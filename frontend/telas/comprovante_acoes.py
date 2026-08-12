from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog, QMessageBox

from services import comprovante_service
from services.api import configuracoes

# ==================================================
# Orquestração das ações do comprovante (Imprimir / Baixar / WhatsApp
# / E-mail) -- compartilhada entre VendaConcluidaDialog (logo após
# fechar a venda) e ComprovanteDialog (reabrir um comprovante antigo),
# pra nao duplicar essa lógica em dois lugares.
# ==================================================


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

    preparado = _preparar(venda_id)

    if not preparado:
        QMessageBox.critical(
            parent, "Erro", "Não foi possível carregar o comprovante."
        )
        return

    _dados, _config, html = preparado

    comprovante_service.imprimir(html, parent)


def baixar_pdf(venda_id, parent):

    preparado = _preparar(venda_id)

    if not preparado:
        QMessageBox.critical(
            parent, "Erro", "Não foi possível carregar o comprovante."
        )
        return

    dados, _config, html = preparado

    comprovante_service.salvar_pdf(
        html, parent, f"comprovante_venda_{dados['venda_id']}.pdf"
    )


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


def enviar_whatsapp(venda_id, parent):

    preparado = _preparar(venda_id)

    if not preparado:
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

    pdf_bytes = comprovante_service.gerar_pdf_bytes(html)

    response = comprovante_service.enviar_whatsapp(
        venda_id,
        pdf_bytes,
        legenda,
        nome_arquivo=f"comprovante_venda_{dados['venda_id']}.pdf",
    )

    if response.status_code == 200:
        QMessageBox.information(
            parent, "Enviado", "Comprovante enviado pelo WhatsApp com sucesso."
        )
        return

    erro = _extrair_erro(response)

    resposta = QMessageBox.question(
        parent,
        "Falha no envio automático",
        f"Não consegui enviar automaticamente:\n\n{erro}\n\n"
        "Quer abrir o WhatsApp manualmente com a mensagem pronta?",
    )

    if resposta == QMessageBox.Yes:
        _abrir_fallback_whatsapp(html, dados, telefone, legenda, parent)


def enviar_email(venda_id, parent):

    preparado = _preparar(venda_id)

    if not preparado:
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

    pdf_bytes = comprovante_service.gerar_pdf_bytes(html)

    response = comprovante_service.enviar_email(
        venda_id,
        pdf_bytes,
        destinatario.strip(),
        assunto=f"Comprovante da sua compra - {nome_loja}",
        corpo=corpo,
        nome_arquivo=f"comprovante_venda_{dados['venda_id']}.pdf",
    )

    if response.status_code == 200:
        QMessageBox.information(
            parent, "Enviado", "Comprovante enviado por e-mail com sucesso."
        )
        return

    QMessageBox.critical(parent, "Falha no envio", _extrair_erro(response))
