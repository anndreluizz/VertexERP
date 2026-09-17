from urllib.parse import quote

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog, QMessageBox

from services import comprovante_service, impressora_termica_service, preferencias_service
from services.api import configuracoes
from services.worker import rodar_em_thread

# ==================================================
# Orquestração das ações do comprovante (Imprimir / Baixar / WhatsApp
# / E-mail) -- compartilhada entre VendaConcluidaDialog (logo após
# fechar a venda) e ComprovanteDialog (reabrir um comprovante antigo),
# pra nao duplicar essa lógica em dois lugares.
# ==================================================


class _Executor(QObject):
    """Ponte pra usar rodar_em_thread() a partir de uma funcao solta
    (nao um metodo de tela) -- as funcoes deste modulo sao chamadas
    por varias telas diferentes (ComprovanteDialog, VendaConcluidaDialog,
    ficha_cliente.py), entao nao ha' um "self" fixo pra servir de
    callback vinculado. Fica parenteada em `parent` (a tela que
    chamou) pra continuar viva pelo tempo da chamada; `rodar()` pode
    ser chamado mais de uma vez em sequencia (ex.: preparar → enviar),
    nunca em paralelo."""

    def __init__(self, parent):
        super().__init__(parent)
        self._ao_pronto = None

    def rodar(self, func, *args, ao_pronto):
        self._ao_pronto = ao_pronto
        rodar_em_thread(self, func, *args, ao_sucesso=self._sucesso, ao_erro=self._erro)

    def _sucesso(self, resultado):
        self._ao_pronto(resultado, None)

    def _erro(self, erro):
        self._ao_pronto(None, erro)


def _preparar(venda_id):
    """Busca dados + config + logo + monta o HTML de uma vez. Retorna
    None (sem mostrar erro -- quem chamou decide o que fazer) se a
    venda não existir mais."""

    dados = comprovante_service.buscar_dados_comprovante(venda_id)

    if not dados:
        return None

    config = configuracoes()
    logo = comprovante_service.obter_logo_loja()
    html = comprovante_service.gerar_html_comprovante(dados, config, logo)

    return dados, config, html


def _extrair_erro(response):
    try:
        return response.json().get("detail") or response.text
    except Exception:
        return response.text


def imprimir(venda_id, parent):

    executor = _Executor(parent)

    def _apos_preparar(preparado, erro):

        if erro is not None or not preparado:
            QMessageBox.critical(
                parent, "Erro", "Não foi possível carregar o comprovante."
            )
            return

        dados, config, html = preparado

        config_impressora = preferencias_service.carregar_impressora_termica()

        if config_impressora and config_impressora.get("ativa"):

            logo = comprovante_service.obter_logo_loja() if config.get("tem_logo") else None

            ok, erro_imp = impressora_termica_service.imprimir_comprovante(
                dados, config, logo, config_impressora
            )

            if ok:
                return

            resposta = QMessageBox.question(
                parent,
                "Falha na impressora térmica",
                f"{erro_imp}\n\nQuer tentar imprimir pela janela normal do Windows?",
            )

            if resposta != QMessageBox.Yes:
                return

        comprovante_service.imprimir(html, parent)

    executor.rodar(_preparar, venda_id, ao_pronto=_apos_preparar)


def baixar_pdf(venda_id, parent):

    executor = _Executor(parent)

    def _apos_preparar(preparado, erro):

        if erro is not None or not preparado:
            QMessageBox.critical(
                parent, "Erro", "Não foi possível carregar o comprovante."
            )
            return

        dados, _config, html = preparado

        comprovante_service.salvar_pdf(
            html, parent, f"comprovante_venda_{dados['venda_id']}.pdf"
        )

    executor.rodar(_preparar, venda_id, ao_pronto=_apos_preparar)


def _abrir_fallback_whatsapp(html, dados, telefone, legenda, parent):
    """Quando não dá pra anexar o PDF automaticamente (integração
    desligada ou falha na Z-API): abre a conversa no WhatsApp já com a
    mensagem pronta, e oferece salvar o PDF pra anexar manualmente."""

    digitos = "".join(c for c in telefone if c.isdigit())

    if len(digitos) <= 11:
        digitos = "55" + digitos

    QDesktopServices.openUrl(
        QUrl(f"https://wa.me/{digitos}?text={quote(legenda)}")
    )

    resposta = QMessageBox.question(
        parent,
        "Compartilhar PDF",
        "Abri o WhatsApp com a mensagem pronta.\n\n"
        "Quer salvar o PDF agora pra anexar manualmente na conversa?",
    )

    if resposta == QMessageBox.Yes:
        comprovante_service.salvar_pdf(
            html, parent, f"comprovante_venda_{dados['venda_id']}.pdf"
        )


def _enviar_whatsapp_request(venda_id, html, legenda, nome_arquivo):
    """Roda na worker thread -- gerar o PDF e' CPU local mas nao vale
    a pena voltar na GUI thread so' pra isso, entao fica junto com o
    POST de envio de verdade."""
    pdf_bytes = comprovante_service.gerar_pdf_bytes(html)
    return comprovante_service.enviar_whatsapp(
        venda_id, pdf_bytes, legenda, nome_arquivo=nome_arquivo
    )


def enviar_whatsapp(venda_id, parent):

    executor = _Executor(parent)

    def _apos_preparar(preparado, erro):

        if erro is not None or not preparado:
            QMessageBox.critical(
                parent, "Erro", "Não foi possível carregar o comprovante."
            )
            return

        dados, config, html = preparado

        telefone = dados.get("cliente_telefone")
        nome_loja = config.get("nome_loja") or "Vertex ERP"
        legenda = comprovante_service.mensagem_whatsapp_padrao(
            dados.get("cliente_nome"), nome_loja
        )

        if not telefone:
            QMessageBox.warning(
                parent,
                "Sem telefone",
                "Este cliente não tem telefone cadastrado.\n\n"
                "Cadastre um telefone na ficha do cliente pra poder "
                "enviar o comprovante automaticamente.",
            )
            return

        if not config.get("whatsapp_ativo"):
            _abrir_fallback_whatsapp(html, dados, telefone, legenda, parent)
            return

        def _apos_enviar(response, erro_envio):

            if erro_envio is not None:
                QMessageBox.critical(parent, "Falha no envio", str(erro_envio))
                return

            if response.status_code == 200:
                QMessageBox.information(
                    parent, "Enviado", "Comprovante enviado pelo WhatsApp com sucesso."
                )
                return

            erro_resp = _extrair_erro(response)

            resposta = QMessageBox.question(
                parent,
                "Falha no envio automático",
                f"Não consegui enviar automaticamente:\n\n{erro_resp}\n\n"
                "Quer abrir o WhatsApp manualmente com a mensagem pronta?",
            )

            if resposta == QMessageBox.Yes:
                _abrir_fallback_whatsapp(html, dados, telefone, legenda, parent)

        executor.rodar(
            _enviar_whatsapp_request,
            venda_id, html, legenda, f"comprovante_venda_{dados['venda_id']}.pdf",
            ao_pronto=_apos_enviar,
        )

    executor.rodar(_preparar, venda_id, ao_pronto=_apos_preparar)


def _enviar_email_request(venda_id, html, destinatario, assunto, corpo, nome_arquivo):
    """Roda na worker thread -- mesmo raciocinio de
    _enviar_whatsapp_request."""
    pdf_bytes = comprovante_service.gerar_pdf_bytes(html)
    return comprovante_service.enviar_email(
        venda_id, pdf_bytes, destinatario,
        assunto=assunto, corpo=corpo, nome_arquivo=nome_arquivo,
    )


def enviar_email(venda_id, parent):

    executor = _Executor(parent)

    def _apos_preparar(preparado, erro):

        if erro is not None or not preparado:
            QMessageBox.critical(
                parent, "Erro", "Não foi possível carregar o comprovante."
            )
            return

        dados, config, html = preparado

        email_padrao = dados.get("cliente_email") or ""

        destinatario, ok = QInputDialog.getText(
            parent,
            "Enviar por E-mail",
            "E-mail do destinatário:",
            text=email_padrao,
        )

        if not ok or not destinatario.strip():
            return

        nome_loja = config.get("nome_loja") or "Vertex ERP"
        corpo = comprovante_service.mensagem_whatsapp_padrao(
            dados.get("cliente_nome"), nome_loja
        )

        def _apos_enviar(response, erro_envio):

            if erro_envio is not None:
                QMessageBox.critical(parent, "Falha no envio", str(erro_envio))
                return

            if response.status_code == 200:
                QMessageBox.information(
                    parent, "Enviado", "Comprovante enviado por e-mail com sucesso."
                )
                return

            QMessageBox.critical(parent, "Falha no envio", _extrair_erro(response))

        executor.rodar(
            _enviar_email_request,
            venda_id, html, destinatario.strip(),
            f"Comprovante da sua compra - {nome_loja}", corpo,
            f"comprovante_venda_{dados['venda_id']}.pdf",
            ao_pronto=_apos_enviar,
        )

    executor.rodar(_preparar, venda_id, ao_pronto=_apos_preparar)
