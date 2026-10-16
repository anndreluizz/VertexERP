from datetime import datetime
from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import (
    QDesktopServices,
)
from PySide6.QtWidgets import (
    QMessageBox,
    QMenu,
)

from services import api
from services.venda_service import listar_vendas
from services.movimento_fiado_service import (
    saldo_cliente,
)
from services.cliente_service import (
    enviar_whatsapp_texto,
)
from services import cliente_analise
from services import comprovante_service
from utils.formatacao import formatar_moeda
from design.widgets import (
    BotaoSecundario,
)


class WhatsAppMixin:
    """Contato do cliente: WhatsApp (comprovante, extrato, cobranca, agradecimento), ligacao e e-mail."""

    def _construir_menu_whatsapp(self):
        """O botão WhatsApp do cabeçalho virou um menu com as ações
        mais usadas -- antes eram vários botões espalhados (inclusive
        "Enviar Último Comprovante", que morava na barra de ações)."""

        menu = QMenu(self)

        menu.addAction("Enviar Último Comprovante", self.enviar_ultimo_comprovante)
        menu.addAction("Enviar Extrato Completo", self.enviar_extrato_whatsapp)
        menu.addAction("Enviar Cobrança", self.enviar_cobranca_whatsapp)
        menu.addAction("Agradecer Pagamento", self.agradecer_pagamento_whatsapp)
        menu.addAction("Agradecer Compra", self.agradecer_compra_whatsapp)

        return menu

    def _botao_contato(self, texto, callback, icone_nome=None):
        """Botão de contato rápido no estilo secundário (fundo claro) --
        ícone só onde existe no pacote Lucide já baixado ('phone' não
        existe, por isso Ligar fica só com texto)."""

        botao = BotaoSecundario(texto, icone_nome=icone_nome)
        botao.setAutoDefault(False)
        if callback:
            botao.clicked.connect(callback)
        return botao

    def _telefone_digitos(self):
        return "".join(c for c in (self.cliente.get("telefone") or "") if c.isdigit())

    def abrir_ligacao(self):

        digitos = self._telefone_digitos()

        if digitos:
            QDesktopServices.openUrl(QUrl(f"tel:{digitos}"))

    def abrir_email(self):

        email = self.cliente.get("email")

        if email:
            QDesktopServices.openUrl(QUrl(f"mailto:{email}"))

    def enviar_ultimo_comprovante(self):
        """Manda um texto pronto com os dados da venda (não mais o PDF
        anexado) -- mesmo padrão de mensagem de texto direta usado nas
        outras duas opções do menu WhatsApp."""

        vendas_cliente = [
            v for v in listar_vendas()
            if v.get("cliente_id") == self.cliente["id"]
        ]

        if not vendas_cliente:
            QMessageBox.information(
                self,
                "Sem compras",
                "Este cliente ainda não tem nenhuma compra registrada.",
            )
            return

        ultima_venda = max(vendas_cliente, key=lambda v: v["data"])

        dados = comprovante_service.buscar_dados_comprovante(ultima_venda["id"])

        if not dados:
            QMessageBox.critical(
                self, "Erro", "Não foi possível carregar os dados da venda."
            )
            return

        data = str(dados.get("data", "")).replace("T", " ")[:16]

        resposta = QMessageBox.question(
            self,
            "Enviar Último Comprovante",
            f"Enviar pelo WhatsApp o comprovante da venda #{dados['venda_id']}"
            f" ({data}, {formatar_moeda(dados['valor_total'])})?",
        )

        if resposta != QMessageBox.Yes:
            return

        nome_loja = api.configuracoes().get("nome_loja") or "Vertex ERP"

        itens_texto = "\n".join(
            f"{item['quantidade']}x {item['nome']} — "
            f"{formatar_moeda(item['subtotal'])}"
            for item in dados.get("itens", [])
        ) or "—"

        if dados.get("forma_pagamento_2"):
            valor_principal = float(dados["valor_total"]) - float(
                dados.get("valor_forma_2") or 0
            )
            pagamento_texto = (
                f"{formatar_moeda(valor_principal)} ({dados['forma_pagamento']}) + "
                f"{formatar_moeda(dados['valor_forma_2'])} ({dados['forma_pagamento_2']})"
            )
        else:
            pagamento_texto = dados.get("forma_pagamento") or "—"

        situacao_texto = (
            "EM ABERTO" if (dados.get("situacao") or "PAGO") == "FIADO" else "PAGO"
        )

        texto = (
            f"Olá, {self.cliente.get('nome', '')}! Tudo bem?\n\n"
            f"Agradecemos pela sua compra na {nome_loja}.\n\n"
            f"COMPROVANTE DE VENDA\n\n"
            f"Data: {data}\n"
            f"Venda nº: {dados['venda_id']}\n\n"
            f"Itens:\n"
            f"{itens_texto}\n\n"
            f"Valor total: {formatar_moeda(dados['valor_total'])}\n"
            f"Forma de pagamento: {pagamento_texto}\n"
            f"Situação: {situacao_texto}\n\n"
            f"Agradecemos pela preferência. Qualquer dúvida, estamos à "
            f"disposição!\n\n"
            f"Equipe {nome_loja}"
        )

        self._enviar_texto_whatsapp(texto, "Enviar Último Comprovante")

    # ======================================
    # MENU "WHATSAPP ▾" -- mensagens de texto livre (extrato, cobrança,
    # saldo, haver, cadastro). Diferente do comprovante (que anexa um
    # PDF), aqui é só texto -- mesmo esquema de fallback manual (abrir
    # o wa.me com a mensagem pronta) usado em comprovante_acoes.py.
    # ======================================

    def _enviar_texto_whatsapp(self, texto, titulo="WhatsApp"):

        telefone = self.cliente.get("telefone")

        if not telefone:
            QMessageBox.warning(
                self,
                "Sem telefone",
                "Este cliente não tem telefone cadastrado.\n\n"
                "Cadastre um telefone na ficha do cliente pra poder "
                "enviar mensagens automaticamente.",
            )
            return

        config = api.configuracoes()

        if not config.get("whatsapp_ativo"):
            self._abrir_fallback_whatsapp(telefone, texto)
            return

        response = enviar_whatsapp_texto(self.cliente["id"], texto)

        if response.status_code == 200:
            QMessageBox.information(
                self, titulo, "Mensagem enviada pelo WhatsApp com sucesso."
            )
            return

        try:
            erro = response.json().get("detail") or response.text
        except Exception:
            erro = response.text

        resposta = QMessageBox.question(
            self,
            "Falha no envio automático",
            f"Não consegui enviar automaticamente:\n\n{erro}\n\n"
            "Quer abrir o WhatsApp manualmente com a mensagem pronta?",
        )

        if resposta == QMessageBox.Yes:
            self._abrir_fallback_whatsapp(telefone, texto)

    def _abrir_fallback_whatsapp(self, telefone, texto):

        digitos = "".join(c for c in telefone if c.isdigit())

        if len(digitos) <= 11:
            digitos = "55" + digitos

        QDesktopServices.openUrl(
            QUrl(f"https://wa.me/{digitos}?text={quote(texto)}")
        )

    def enviar_extrato_whatsapp(self):
        """'Extrato Completo' -- resumo financeiro curto (total
        comprado, total pago, saldo em aberto), não mais o extrato
        movimento a movimento -- mensagem mais direta pro WhatsApp."""

        saldo = saldo_cliente(self.cliente["id"])

        agr = cliente_analise.calcular_agregados(
            self.cliente, [mov for mov, _ in reversed(self._movimentos)]
        )

        total_pago = sum(
            float(mov.get("valor", 0) or 0)
            for mov, _ in self._movimentos
            if mov.get("tipo") == "PAGAMENTO"
        )

        nome_loja = api.configuracoes().get("nome_loja") or "Vertex ERP"
        hoje = datetime.now().strftime("%d/%m/%Y")

        texto = (
            f"Olá, {self.cliente.get('nome', '')}! Tudo bem?\n\n"
            f"Segue o resumo atualizado do seu cadastro na {nome_loja}:\n\n"
            f"EXTRATO FINANCEIRO\n\n"
            f"Total de compras: {formatar_moeda(agr['total_comprado'])}\n"
            f"Total já pago: {formatar_moeda(total_pago)}\n"
            f"Saldo atual em aberto: {formatar_moeda(saldo)}\n\n"
            f"Última atualização: {hoje}\n\n"
            f"Caso queira conferir alguma compra ou pagamento, é só nos "
            f"chamar. Será um prazer ajudar!\n\n"
            f"Equipe {nome_loja}"
        )

        self._enviar_texto_whatsapp(texto, "Extrato Completo")

    def enviar_cobranca_whatsapp(self):
        """Mensagem de cobrança -- só faz sentido quando existe saldo
        devedor de verdade."""

        saldo = saldo_cliente(self.cliente["id"])

        if saldo <= 0:
            QMessageBox.information(
                self, "Cobrança", "Este cliente não tem saldo devedor."
            )
            return

        nome_loja = api.configuracoes().get("nome_loja") or "Vertex ERP"

        texto = (
            f"Olá, {self.cliente.get('nome', '')}! Tudo bem?\n\n"
            f"Estamos passando para lembrar, de forma amigável, que "
            f"consta em nosso sistema um saldo em aberto referente às "
            f"suas compras na {nome_loja}.\n\n"
            f"Saldo pendente: {formatar_moeda(saldo)}\n\n"
            f"Se o pagamento já foi realizado, por favor, desconsidere "
            f"esta mensagem. Caso precise conferir o histórico das "
            f"compras, combinar uma data ou tirar alguma dúvida, "
            f"estamos à disposição.\n\n"
            f"Agradecemos a sua atenção e preferência!\n\n"
            f"Equipe {nome_loja}"
        )

        self._enviar_texto_whatsapp(texto, "Enviar Cobrança")

    def agradecer_compra_whatsapp(self):
        # compra: so' o obrigado, sem valor nem saldo (pedido do usuario)
        self._enviar_agradecimento("Muito obrigado pela sua compra!", com_saldo=False)

    def agradecer_pagamento_whatsapp(self):
        """Obrigado pelo último pagamento, com o saldo que ficou."""

        ultimo = next(
            (mov for mov, _ in self._movimentos if mov.get("tipo") == "PAGAMENTO"),
            None,
        )
        if not ultimo:
            QMessageBox.information(
                self, "Agradecimento", "Este cliente ainda não tem pagamento registrado."
            )
            return

        valor = formatar_moeda(float(ultimo.get("valor", 0) or 0))
        self._enviar_agradecimento(f"Muito obrigado pelo seu pagamento de {valor}!")

    def _enviar_agradecimento(self, agradecimento, com_saldo=True):
        """Pagamento: com o saldo que ficou; compra: só o obrigado.
        Sem telefone, _enviar_texto_whatsapp já avisa."""

        if not self.cliente.get("telefone"):
            self._enviar_texto_whatsapp("", "Agradecimento")
            return

        nome_loja = api.configuracoes().get("nome_loja") or "Vertex ERP"
        restante = ""
        if com_saldo:
            saldo = saldo_cliente(self.cliente["id"])
            restante = (
                f"Saldo restante da sua conta: {formatar_moeda(saldo)}"
                if saldo > 0.009 else "Sua conta está quitada!"
            ) + "\n\n"

        texto = (
            f"Olá, {self.cliente.get('nome', '')}! Tudo bem?\n\n"
            f"{agradecimento}\n\n"
            f"{restante}"
            f"Agradecemos a preferência!\n\n"
            f"Equipe {nome_loja}"
        )

        self._enviar_texto_whatsapp(texto, "Agradecimento")
