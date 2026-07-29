from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument, QFont, QPageSize
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

    def texto_comprovante(self):

        config = configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"

        linhas = [
            nome_loja.center(40),
            "-" * 40,
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            "-" * 40,
        ]

        for item in self.itens:

            subtotal = item["preco"] * item["quantidade"]

            linhas.append(
                f"{item['quantidade']}x {item['nome']}"
            )
            linhas.append(
                f"  R$ {item['preco']:.2f}".rjust(20)
                + f"= R$ {subtotal:.2f}".rjust(20)
            )

        linhas.append("-" * 40)
        linhas.append(f"TOTAL: R$ {self.total:.2f}".rjust(40))

        if self.forma_pagamento_2:
            valor_principal = self.total - self.valor_forma_2
            linhas.append(
                f"Pagamento: R$ {valor_principal:.2f} "
                f"({self.forma_pagamento}) + "
                f"R$ {self.valor_forma_2:.2f} "
                f"({self.forma_pagamento_2})"
            )
        else:
            linhas.append(
                f"Forma de pagamento: {self.forma_pagamento}"
            )

        linhas.append("-" * 40)
        linhas.append("Este comprovante não tem valor fiscal.")

        return "\n".join(linhas)

    def montar_documento(self, texto):

        documento = QTextDocument()
        documento.setDefaultFont(QFont("Consolas", 10))
        documento.setPlainText(texto)

        return documento

    def emitir_comprovante(self):

        texto = self.texto_comprovante()

        janela = QDialog(self)
        janela.setWindowTitle("Comprovante (não fiscal)")
        janela.setFixedSize(380, 500)

        v = QVBoxLayout(janela)

        area = QTextEdit()
        area.setReadOnly(True)
        area.setStyleSheet("font-family: Consolas, monospace;")
        area.setText(texto)

        botoes = QHBoxLayout()

        bt_pdf = QPushButton("Salvar PDF")
        bt_pdf.clicked.connect(
            lambda: self.salvar_pdf(texto)
        )

        bt_imprimir = QPushButton("Imprimir")
        bt_imprimir.clicked.connect(
            lambda: self.imprimir(texto, janela)
        )

        bt_fechar = QPushButton("Fechar")
        bt_fechar.clicked.connect(janela.accept)

        botoes.addWidget(bt_pdf)
        botoes.addWidget(bt_imprimir)
        botoes.addWidget(bt_fechar)

        v.addWidget(area)
        v.addLayout(botoes)

        janela.exec()

    def salvar_pdf(self, texto):

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

        self.montar_documento(texto).print_(printer)

        QMessageBox.information(
            self,
            "Sucesso",
            "Comprovante salvo em PDF com sucesso.",
        )

    def imprimir(self, texto, parent):

        printer = QPrinter(QPrinter.HighResolution)

        dialogo = QPrintDialog(printer, parent)

        if dialogo.exec() != QPrintDialog.Accepted:
            return

        self.montar_documento(texto).print_(printer)
