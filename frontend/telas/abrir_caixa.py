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
from services.worker import rodar_em_thread

from design import tokens
from design.icons import icone, icone_pixmap
from design.responsive import tamanho_fixo_seguro
from design.widgets import Badge, BotaoSecundario, BotaoSucesso
from utils.formatacao import formatar_moeda

VALORES_RAPIDOS = [50, 100, 150, 200, 300, 500]


class AbrirCaixaWindow(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Abrir Caixa")
        tamanho_fixo_seguro(self, 460, 640)
        self.setStyleSheet(f"background:{tokens.CARD};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ======================
        # CORPO (com cabeçalho embutido -- ícone + título + fechar,
        # mesmo padrão dos diálogos da ficha do cliente)
        # ======================

        corpo = QVBoxLayout()
        corpo.setContentsMargins(24, 22, 24, 20)
        corpo.setSpacing(14)

        linha_cabecalho = QHBoxLayout()
        linha_cabecalho.setSpacing(14)

        icone_circulo = QLabel()
        icone_circulo.setFixedSize(48, 48)
        icone_circulo.setAlignment(Qt.AlignCenter)
        icone_circulo.setStyleSheet(f"""
            background:{tokens.SUCESSO_CLARO}; border-radius:24px;
        """)
        icone_circulo.setPixmap(
            icone_pixmap("wallet", cor=tokens.SECUNDARIA_HOVER, tamanho=20)
        )
        linha_cabecalho.addWidget(icone_circulo)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(2)

        titulo = QLabel("Abrir Caixa")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel("Informe o troco inicial para liberar o caixa")
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        linha_cabecalho.addLayout(col_titulo, 1)

        bt_fechar = QPushButton()
        bt_fechar.setFixedSize(30, 30)
        bt_fechar.setCursor(Qt.PointingHandCursor)
        bt_fechar.setAutoDefault(False)
        bt_fechar.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        bt_fechar.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        bt_fechar.clicked.connect(self.reject)
        linha_cabecalho.addWidget(bt_fechar, 0, Qt.AlignTop)

        corpo.addLayout(linha_cabecalho)

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

        # so' essa secao do dialogo depende de rede -- o resto (campo
        # de valor, atalhos, rodape) ja pinta na hora; sem isso, o
        # dialogo inteiro demorava pra aparecer esperando o historico
        rodar_em_thread(
            self,
            historico_caixa,
            ao_sucesso=self._ao_historico_sucesso,
            ao_erro=self._ao_historico_erro,
        )

    def _ao_historico_erro(self, erro):

        while self.historico_layout.count():
            item = self.historico_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        vazio = QLabel(f"Não foi possível carregar o histórico.\n{erro}")
        vazio.setWordWrap(True)
        vazio.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        self.historico_layout.addWidget(vazio, 0, 0, 1, 3)

    def _ao_historico_sucesso(self, sessoes):

        while self.historico_layout.count():
            item = self.historico_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        sessoes = sessoes[:3]

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
            lbl_saldo = QLabel(formatar_moeda(saldo))
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
