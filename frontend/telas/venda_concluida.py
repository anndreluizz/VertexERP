from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)

from design import tokens
from design.animations import fade_in
from design.responsive import tamanho_fixo_seguro
from design.widgets import BotaoPrimario, BotaoSecundario, BotaoSucesso
from telas import comprovante_acoes
from telas.comprovante_dialog import ComprovanteDialog


class VendaConcluidaDialog(QDialog):

    def __init__(
        self,
        venda_id,
        total,
        itens,
        forma_pagamento,
        cliente_nome=None,
        forma_pagamento_2=None,
        valor_forma_2=None,
        parent=None,
    ):

        super().__init__(parent)

        self.venda_id = venda_id
        self.total = total
        self.itens = itens
        self.forma_pagamento = forma_pagamento
        self.cliente_nome = cliente_nome
        self.forma_pagamento_2 = forma_pagamento_2
        self.valor_forma_2 = valor_forma_2 or 0.0

        self.setWindowTitle("Venda Finalizada")
        tamanho_fixo_seguro(self, 440, 640)
        self.setStyleSheet("background:white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignHCenter)

        selo = QLabel("✓")
        selo.setFixedSize(80, 80)
        selo.setAlignment(Qt.AlignCenter)
        selo.setStyleSheet("""
            background:#2E7D32;
            color:white;
            font-size:40px;
            font-weight:bold;
            border-radius:40px;
        """)

        titulo = QLabel("Pago!")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(
            "background:transparent; font-size:24px; font-weight:bold; "
            "color:#202225;"
        )

        subtitulo = QLabel(f"VENDA #{venda_id} FINALIZADA")
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setStyleSheet(
            "background:transparent; font-size:11px; color:gray; "
            "font-weight:bold;"
        )

        valor = QLabel(f"R$ {total:.2f}")
        valor.setAlignment(Qt.AlignCenter)
        valor.setStyleSheet(
            "background:transparent; font-size:30px; font-weight:bold; "
            "color:#2E7D32;"
        )

        layout.addWidget(selo, alignment=Qt.AlignHCenter)
        layout.addSpacing(4)
        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(8)
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

            layout.addSpacing(8)
            layout.addWidget(lbl_fiado)

        layout.addSpacing(16)

        # ======================
        # AÇÕES DO COMPROVANTE
        # ======================

        self.bt_visualizar = BotaoPrimario(
            "Visualizar Comprovante", icone_nome="file-text"
        )
        self.bt_visualizar.setMinimumHeight(48)
        self.bt_visualizar.clicked.connect(self.visualizar_comprovante)
        layout.addWidget(self.bt_visualizar)

        linha_acoes = QHBoxLayout()
        linha_acoes.setSpacing(8)

        self.bt_imprimir = BotaoSecundario("Imprimir", icone_nome="printer")
        self.bt_imprimir.setMinimumHeight(44)
        self.bt_imprimir.clicked.connect(self.imprimir)

        self.bt_baixar = BotaoSecundario("Baixar PDF", icone_nome="download")
        self.bt_baixar.setMinimumHeight(44)
        self.bt_baixar.clicked.connect(self.baixar_pdf)

        linha_acoes.addWidget(self.bt_imprimir)
        linha_acoes.addWidget(self.bt_baixar)
        layout.addLayout(linha_acoes)

        linha_envio = QHBoxLayout()
        linha_envio.setSpacing(8)

        self.bt_whatsapp = BotaoSecundario(
            "WhatsApp", icone_nome="message-circle"
        )
        self.bt_whatsapp.setMinimumHeight(44)
        self.bt_whatsapp.clicked.connect(self.enviar_whatsapp)

        self.bt_email = BotaoSecundario("E-mail", icone_nome="mail")
        self.bt_email.setMinimumHeight(44)
        self.bt_email.clicked.connect(self.enviar_email)

        linha_envio.addWidget(self.bt_whatsapp)
        linha_envio.addWidget(self.bt_email)
        layout.addLayout(linha_envio)

        layout.addSpacing(8)

        self.bt_nova_venda = BotaoSucesso("Abrir Nova Venda")
        self.bt_nova_venda.setMinimumHeight(48)
        self.bt_nova_venda.clicked.connect(self.accept)
        layout.addWidget(self.bt_nova_venda)

        fade_in(self, duracao=220)

    # ======================
    # AÇÕES
    # ======================

    def visualizar_comprovante(self):
        ComprovanteDialog(self.venda_id, parent=self).exec()

    def imprimir(self):
        comprovante_acoes.imprimir(self.venda_id, self)

    def baixar_pdf(self):
        comprovante_acoes.baixar_pdf(self.venda_id, self)

    def enviar_whatsapp(self):
        comprovante_acoes.enviar_whatsapp(self.venda_id, self)

    def enviar_email(self):
        comprovante_acoes.enviar_email(self.venda_id, self)
