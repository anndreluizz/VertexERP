from PySide6.QtWidgets import QDoubleSpinBox, QMessageBox

from design import tokens
from design.widgets import BotaoPerigo, CampoTexto, DialogoPadrao, campo_rotulado


class MovimentoGavetaDialog(DialogoPadrao):
    """Base de Sangria e Suprimento (eram dois arquivos quase iguais):
    valor + motivo, no molde padrão das subtelas."""

    TIPO = ""

    def __init__(self, titulo, subtitulo, icone_nome, cor, cor_fundo, placeholder, botao):

        super().__init__(
            titulo, subtitulo, icone_nome, cor, cor_fundo,
            largura=DialogoPadrao.PEQUENO,
        )

        self.valor = QDoubleSpinBox()
        self.valor.setMinimum(0)
        self.valor.setMaximum(99999999)
        self.valor.setDecimals(2)
        self.valor.setPrefix("R$ ")
        self.valor.setMinimumHeight(52)
        self.valor.setStyleSheet(f"""
            QDoubleSpinBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_XL}px; font-weight: 800;
                color: {cor}; background: {tokens.CARD};
            }}
            QDoubleSpinBox:focus {{ border-color: {cor}; }}
        """)

        self.descricao = CampoTexto(placeholder)

        self.corpo.addWidget(campo_rotulado("Valor", self.valor))
        self.corpo.addWidget(campo_rotulado("Motivo", self.descricao))
        self.corpo.addStretch()

        self.bt_confirmar = botao
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.clicked.connect(self.confirmar)
        self.bt_cancelar = self.definir_botoes(self.bt_confirmar)

        self.ajustar_altura()
        self.valor.setFocus()
        self.valor.selectAll()

    @property
    def dados(self):

        return {
            "tipo": self.TIPO,
            "valor": float(self.valor.value()),
            "descricao": self.descricao.text(),
        }

    def confirmar(self):

        if self.valor.value() <= 0:
            QMessageBox.warning(self, "Aviso", "Informe um valor.")
            self.valor.setFocus()
            return

        if self.descricao.text().strip() == "":
            QMessageBox.warning(self, "Aviso", "Informe uma descrição.")
            self.descricao.setFocus()
            return

        self.accept()


class SangriaWindow(MovimentoGavetaDialog):

    TIPO = "SANGRIA"

    def __init__(self):
        super().__init__(
            "Sangria", "Retirada de dinheiro da gaveta",
            "arrow-down", tokens.ERRO, tokens.ERRO_CLARO,
            "Motivo da sangria", BotaoPerigo("Confirmar Sangria", icone_nome="check"),
        )
