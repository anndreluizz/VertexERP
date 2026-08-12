from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QMessageBox,
)

from services.caixa_service import historico_caixa

from design import tokens
from design.widgets import Badge, BotaoSecundario, BotaoSucesso

VALORES_RAPIDOS = [50, 100, 150, 200, 300, 500]


class AbrirCaixaWindow(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Abrir Caixa")
        self.setFixedSize(460, 640)
        self.setStyleSheet(f"background:{tokens.CARD};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QFrame()
        cabecalho.setStyleSheet(f"background:{tokens.SIDEBAR};")
        cabecalho.setFixedHeight(70)

        cab_layout = QVBoxLayout(cabecalho)
        cab_layout.setContentsMargins(24, 12, 24, 12)
        cab_layout.setSpacing(2)

        titulo = QLabel("ABRIR CAIXA")
        titulo.setStyleSheet(f"""
            background:transparent; color:white;
            font-size:{tokens.TAMANHO_LG}px; font-weight:800;
        """)

        subtitulo = QLabel("Informe o troco inicial para liberar o caixa")
        subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        cab_layout.addWidget(titulo)
        cab_layout.addWidget(subtitulo)

        raiz.addWidget(cabecalho)

        # ======================
        # CORPO
        # ======================

        corpo = QVBoxLayout()
        corpo.setContentsMargins(24, 20, 24, 20)
        corpo.setSpacing(14)

        lbl_valor_titulo = QLabel("VALOR INICIAL (TROCO)")
        lbl_valor_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.valor = QLineEdit()
        self.valor.setPlaceholderText("R$ 0,00")
        self.valor.setAlignment(Qt.AlignCenter)
        self.valor.setStyleSheet(f"""
            QLineEdit {{
                font-size:38px; font-weight:800; color:{tokens.SECUNDARIA};
                border:none; border-bottom:2px solid {tokens.BORDA};
                padding:6px 0; background:transparent;
            }}
        """)

        corpo.addWidget(lbl_valor_titulo)
        corpo.addWidget(self.valor)

        valores_layout = QGridLayout()
        valores_layout.setSpacing(8)

        for indice, valor in enumerate(VALORES_RAPIDOS):

            bt = QPushButton(f"R$ {valor}")
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(38)
            bt.setStyleSheet(f"""
                QPushButton {{
                    background:{tokens.FUNDO}; color:{tokens.TEXTO};
                    border-radius:{tokens.RADIUS_SM}px; font-weight:700;
                }}
                QPushButton:hover {{ background:{tokens.BORDA}; }}
            """)
            bt.clicked.connect(
                lambda checked, v=valor: self.definir_valor(v)
            )

            valores_layout.addWidget(bt, indice // 3, indice % 3)

        corpo.addLayout(valores_layout)

        # ======================
        # HISTÓRICO DE SESSÕES
        # ======================

        lbl_historico_titulo = QLabel("ÚLTIMAS SESSÕES")
        lbl_historico_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        corpo.addWidget(lbl_historico_titulo)

        historico_frame = QFrame()
        historico_frame.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
        """)

        self.historico_layout = QGridLayout(historico_frame)
        self.historico_layout.setContentsMargins(12, 10, 12, 10)
        self.historico_layout.setHorizontalSpacing(12)
        self.historico_layout.setVerticalSpacing(6)
        self.historico_layout.setColumnStretch(0, 1)
        self.historico_layout.setColumnStretch(2, 1)

        corpo.addWidget(historico_frame)

        self.carregar_historico()

        corpo.addStretch()

        raiz.addLayout(corpo)

        # ======================
        # RODAPÉ
        # ======================

        rodape = QFrame()
        rodape.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-top:1px solid {tokens.BORDA};
        """)

        rodape_layout = QHBoxLayout(rodape)
        rodape_layout.setContentsMargins(24, 14, 24, 14)
        rodape_layout.setSpacing(10)

        self.bt_cancelar = BotaoSecundario("Cancelar")
        self.bt_cancelar.setMinimumHeight(46)

        self.bt_abrir = BotaoSucesso("Abrir Caixa")
        self.bt_abrir.setMinimumHeight(46)

        rodape_layout.addWidget(self.bt_cancelar)
        rodape_layout.addWidget(self.bt_abrir)

        raiz.addWidget(rodape)

        self.bt_cancelar.clicked.connect(self.reject)
        self.bt_abrir.clicked.connect(self.confirmar)

    # ======================================

    def definir_valor(self, valor):
        self.valor.setText(f"{valor:.2f}")

    def carregar_historico(self):

        while self.historico_layout.count():
            item = self.historico_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        sessoes = historico_caixa()[:3]

        if not sessoes:
            vazio = QLabel("Nenhuma sessão registrada ainda.")
            vazio.setStyleSheet(f"""
                background:transparent; font-size:{tokens.TAMANHO_SM}px;
                color:{tokens.TEXTO_TERCIARIO};
            """)
            self.historico_layout.addWidget(vazio, 0, 0, 1, 3)
            return

        for linha_indice, sessao in enumerate(sessoes):

            data = str(sessao.get("data_abertura", ""))[:16]
            data = data.replace("T", " ")

            status = sessao.get("status", "")

            lbl_data = QLabel(data)
            lbl_data.setStyleSheet(f"""
                background:transparent; font-size:{tokens.TAMANHO_SM}px;
                color:{tokens.TEXTO};
            """)

            badge_status = Badge(
                status, "sucesso" if status == "ABERTO" else "neutro"
            )

            saldo = float(sessao.get("saldo_final", 0) or 0)
            lbl_saldo = QLabel(f"R$ {saldo:.2f}")
            lbl_saldo.setAlignment(Qt.AlignRight)
            lbl_saldo.setStyleSheet(f"""
                background:transparent; font-size:{tokens.TAMANHO_SM}px;
                color:{tokens.TEXTO};
            """)

            self.historico_layout.addWidget(lbl_data, linha_indice, 0)
            self.historico_layout.addWidget(
                badge_status, linha_indice, 1, Qt.AlignCenter
            )
            self.historico_layout.addWidget(lbl_saldo, linha_indice, 2)

    def confirmar(self):

        try:
            valor = float(self.valor.text().replace(",", "."))
        except ValueError:
            valor = 0

        if valor < 0:
            QMessageBox.warning(
                self,
                "Atenção",
                "Informe um valor inicial válido.",
            )
            return

        self.accept()

    @property
    def saldo(self):
        try:
            return float(self.valor.text().replace(",", "."))
        except ValueError:
            return 0.0
