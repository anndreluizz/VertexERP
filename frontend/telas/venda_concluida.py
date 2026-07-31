from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument, QPageSize
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

from services.api import configuracoes


class VendaConcluidaDialog(QDialog):

    def __init__(
        self,
        total,
        itens,
        forma_pagamento,
        cliente_nome=None,
        forma_pagamento_2=None,
        valor_forma_2=None,
        parent=None,
    ):

        super().__init__(parent)

        self.total = total
        self.itens = itens
        self.forma_pagamento = forma_pagamento
        self.cliente_nome = cliente_nome
        self.forma_pagamento_2 = forma_pagamento_2
        self.valor_forma_2 = valor_forma_2 or 0.0

        self.setWindowTitle("Venda Finalizada")
        self.setFixedSize(420, 520)
        self.setStyleSheet("background:white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignHCenter)

        selo = QLabel("✓")
        selo.setFixedSize(90, 90)
        selo.setAlignment(Qt.AlignCenter)
        selo.setStyleSheet("""
            background:#2E7D32;
            color:white;
            font-size:44px;
            font-weight:bold;
            border-radius:45px;
        """)

        titulo = QLabel("Pago!")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(
            "background:transparent; font-size:26px; font-weight:bold; "
            "color:#202225;"
        )

        subtitulo = QLabel("VENDA FINALIZADA")
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setStyleSheet(
            "background:transparent; font-size:11px; color:gray; "
            "font-weight:bold;"
        )

        valor = QLabel(f"R$ {total:.2f}")
        valor.setAlignment(Qt.AlignCenter)
        valor.setStyleSheet(
            "background:transparent; font-size:34px; font-weight:bold; "
            "color:#2E7D32;"
        )

        layout.addWidget(selo, alignment=Qt.AlignHCenter)
        layout.addSpacing(6)
        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(10)
        layout.addWidget(valor)

        tem_fiado = (
            forma_pagamento == "PRAZO"
            or forma_pagamento_2 == "PRAZO"
        )

        if tem_fiado and cliente_nome:

            texto_fiado = (
                f"Fiado de {cliente_nome}"
                if forma_pagamento == "PRAZO"
                else (
                    f"Fiado de {cliente_nome} — "
                    f"R$ {self.valor_forma_2:.2f}"
                )
            )

            lbl_fiado = QLabel(texto_fiado)
            lbl_fiado.setAlignment(Qt.AlignCenter)
            lbl_fiado.setWordWrap(True)
            lbl_fiado.setStyleSheet("""
                background:#FFF3E0;
                color:#E65100;
                font-size:13px;
                font-weight:bold;
                border-radius:8px;
                padding:8px 14px;
            """)

            layout.addSpacing(10)
            layout.addWidget(lbl_fiado)

        layout.addSpacing(20)

        self.bt_comprovante = QPushButton("🧾  Emitir Comprovante")
        self.bt_comprovante.setMinimumHeight(48)
        self.bt_comprovante.setStyleSheet("""
            QPushButton {
                background:#202225;
                color:white;
                border-radius:8px;
                font-weight:bold;
            }
            QPushButton:hover {
                background:#33363b;
            }
        """)
        self.bt_comprovante.clicked.connect(self.emitir_comprovante)

        self.bt_nova_venda = QPushButton("Abrir Nova Venda")
        self.bt_nova_venda.setMinimumHeight(48)
        self.bt_nova_venda.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                border-radius:8px;
                font-weight:bold;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        self.bt_nova_venda.clicked.connect(self.accept)

        layout.addWidget(self.bt_comprovante)
        layout.addWidget(self.bt_nova_venda)

    def html_comprovante(self):
        """Comprovante moderno em HTML — mesmo padrão de
        QTextDocument+QPrinter já usado em ficha_cliente.py, no lugar
        do texto monoespaçado antigo."""

        config = configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"

        linhas_itens = "".join(
            "<tr>"
            f"<td style='padding:6px 8px; border-bottom:1px solid #E5E7EB;'>"
            f"{item['nome']}</td>"
            f"<td style='padding:6px 8px; border-bottom:1px solid #E5E7EB; "
            f"text-align:center;'>{item['quantidade']}</td>"
            f"<td style='padding:6px 8px; border-bottom:1px solid #E5E7EB; "
            f"text-align:right;'>R$ {item['preco']:.2f}</td>"
            f"<td style='padding:6px 8px; border-bottom:1px solid #E5E7EB; "
            f"text-align:right;'>R$ {item['preco'] * item['quantidade']:.2f}</td>"
            "</tr>"
            for item in self.itens
        )

        if self.forma_pagamento_2:
            valor_principal = self.total - self.valor_forma_2
            linha_pagamento = (
                f"<p style='margin:4px 0;'>Pagamento: "
                f"R$ {valor_principal:.2f} ({self.forma_pagamento}) + "
                f"R$ {self.valor_forma_2:.2f} ({self.forma_pagamento_2})</p>"
            )
        else:
            linha_pagamento = (
                f"<p style='margin:4px 0;'>Forma de pagamento: "
                f"{self.forma_pagamento}</p>"
            )

        cliente_linha = (
            f"<p style='margin:4px 0;'>Cliente: {self.cliente_nome}</p>"
            if self.cliente_nome else ""
        )

        return f"""
        <html>
        <body style="font-family: Arial; font-size: 13px; color:#1E293B;">
            <h2 style="margin-bottom:0; text-align:center;">{nome_loja}</h2>
            <p style="color:#64748B; margin-top:2px; text-align:center;">
                {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </p>
            <hr style="border:none; border-top:1px solid #E5E7EB;">
            {cliente_linha}
            <table style="width:100%; border-collapse:collapse; margin-top:8px;">
                <tr style="background:#F1F5F9;">
                    <th style="padding:6px 8px; text-align:left;">Produto</th>
                    <th style="padding:6px 8px;">Qtd</th>
                    <th style="padding:6px 8px; text-align:right;">Unitário</th>
                    <th style="padding:6px 8px; text-align:right;">Subtotal</th>
                </tr>
                {linhas_itens}
            </table>
            <h3 style="text-align:right; margin-top:12px;">
                Total: R$ {self.total:.2f}
            </h3>
            {linha_pagamento}
            <hr style="border:none; border-top:1px solid #E5E7EB;">
            <p style="color:#94A3B8; font-size:11px; text-align:center;">
                Este comprovante não tem valor fiscal.
            </p>
        </body>
        </html>
        """

    def montar_documento(self, html):

        documento = QTextDocument()
        documento.setHtml(html)

        return documento

    def emitir_comprovante(self):

        html = self.html_comprovante()

        janela = QDialog(self)
        janela.setWindowTitle("Comprovante (não fiscal)")
        janela.setFixedSize(380, 500)

        v = QVBoxLayout(janela)

        area = QTextEdit()
        area.setReadOnly(True)
        area.setHtml(html)

        botoes = QHBoxLayout()

        bt_pdf = QPushButton("Salvar PDF")
        bt_pdf.clicked.connect(
            lambda: self.salvar_pdf(html)
        )

        bt_imprimir = QPushButton("Imprimir")
        bt_imprimir.clicked.connect(
            lambda: self.imprimir(html, janela)
        )

        bt_fechar = QPushButton("Fechar")
        bt_fechar.clicked.connect(janela.accept)

        botoes.addWidget(bt_pdf)
        botoes.addWidget(bt_imprimir)
        botoes.addWidget(bt_fechar)

        v.addWidget(area)
        v.addLayout(botoes)

        janela.exec()

    def salvar_pdf(self, html):

        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Comprovante",
            "comprovante.pdf",
            "Arquivo PDF (*.pdf)",
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(caminho)
        printer.setPageSize(QPageSize(QPageSize.A5))

        self.montar_documento(html).print_(printer)

        QMessageBox.information(
            self,
            "Sucesso",
            "Comprovante salvo em PDF com sucesso.",
        )

    def imprimir(self, html, parent):

        printer = QPrinter(QPrinter.HighResolution)

        dialogo = QPrintDialog(printer, parent)

        if dialogo.exec() != QPrintDialog.Accepted:
            return

        self.montar_documento(html).print_(printer)
