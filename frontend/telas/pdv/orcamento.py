from datetime import datetime

from services.api import configuracoes
from services import comprovante_service
from utils.documento_html import (
    ESTILO_BODY,
    bloco_total,
    cabecalho_html,
    cabecalho_tabela,
    linha_zebra,
    rodape_nao_fiscal,
)
from PySide6.QtGui import (
    QTextDocument,
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QMessageBox,
    QFileDialog,
)
from design import tokens
from design.widgets import (
    BotaoPrimario,
    BotaoSecundario,
)
from utils.formatacao import formatar_moeda, formatar_quantidade, subtotal_item


class OrcamentoMixin:
    """Orcamento: impressao e PDF do carrinho atual."""

    # ==================================================
    # ORÇAMENTO — imprime/exporta o carrinho atual sem finalizar a
    # venda. Não fica salvo nem listável em nenhum lugar: se virar
    # venda de verdade, é só continuar normalmente e ir em "Pagar".
    # ==================================================

    def imprimir_orcamento(self):

        if not self.itens:
            QMessageBox.warning(
                self, "Aviso", "Não há itens no carrinho pra gerar um orçamento."
            )
            return

        documento = self._montar_documento_orcamento()

        janela = QDialog(self)
        janela.setWindowTitle("Orçamento")
        janela.setFixedSize(360, 230)
        janela.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(janela)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        lbl = QLabel(
            "O orçamento não gera nenhuma venda — é só um documento "
            "pra levar ou enviar ao cliente."
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(lbl)

        bt_imprimir = BotaoPrimario("Imprimir", icone_nome="printer")
        bt_imprimir.clicked.connect(
            lambda: self._imprimir_documento(documento, janela)
        )

        bt_pdf = BotaoSecundario("Salvar PDF")
        bt_pdf.clicked.connect(lambda: self._salvar_pdf_documento(documento))

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.clicked.connect(janela.accept)

        layout.addWidget(bt_imprimir)
        layout.addWidget(bt_pdf)
        layout.addWidget(bt_fechar)

        janela.exec()

    def _montar_documento_orcamento(self):

        config = configuracoes()
        logo_bytes = comprovante_service.obter_logo_loja()

        subtotal = sum(subtotal_item(item["preco"], item["quantidade"]) for item in self.itens)
        total = max(0.0, subtotal - self.desconto_valor + self.acrescimo_valor)

        linhas_itens = "".join(
            linha_zebra(
                [
                    item["nome"],
                    formatar_quantidade(item["quantidade"], item.get("unidade")),
                    formatar_moeda(item["preco"]),
                    formatar_moeda(subtotal_item(item["preco"], item["quantidade"])),
                ],
                indice,
                alinhamentos=["left", "center", "right", "right"],
            )
            for indice, item in enumerate(self.itens)
        )

        cliente_linha = (
            f"<p style='margin:4px 0;'>Cliente: {self.cliente_nome}</p>"
            if self.cliente_nome else ""
        )

        html = f"""
        <html>
        <body style="{ESTILO_BODY}">
            {cabecalho_html("ORÇAMENTO", config, logo_bytes)}
            <p style="margin:4px 0;">
                Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </p>
            {cliente_linha}
            <table style="width:100%; border-collapse:collapse; border:1px solid #E5E7EB; margin-top:12px;">
                {cabecalho_tabela(
                    ["Produto", "Qtd", "Unitário", "Subtotal"],
                    ["left", "center", "right", "right"],
                )}
                {linhas_itens}
            </table>
            {bloco_total("TOTAL", formatar_moeda(total))}
            {rodape_nao_fiscal(
                "Este orçamento não tem valor fiscal e não gera nenhuma "
                "venda. Os valores podem mudar até a confirmação da compra."
            )}
        </body>
        </html>
        """

        documento = QTextDocument()
        documento.setHtml(html)

        return documento

    def _imprimir_documento(self, documento, parent):

        printer = QPrinter(QPrinter.HighResolution)
        dialogo = QPrintDialog(printer, parent)

        if dialogo.exec() != QPrintDialog.Accepted:
            return

        documento.print_(printer)

    def _salvar_pdf_documento(self, documento):

        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar Orçamento", "orcamento.pdf", "Arquivo PDF (*.pdf)",
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(caminho)

        documento.print_(printer)

        QMessageBox.information(
            self, "Sucesso", "Orçamento salvo em PDF com sucesso."
        )
