from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QMessageBox,
)

from services import api
from services.caixa_service import historico_caixa
from services.worker import rodar_em_thread

from design import tokens
from design.widgets import Badge, BotaoSucesso, DialogoPadrao, campo_rotulado, titulo_secao
from utils.formatacao import formatar_moeda

VALORES_RAPIDOS = [50, 100, 150, 200, 300, 500]


class AbrirCaixaWindow(DialogoPadrao):

    def __init__(self):
        super().__init__(
            "Abrir Caixa", "Informe o troco inicial para liberar o caixa",
            "wallet", tokens.SECUNDARIA_HOVER, tokens.SUCESSO_CLARO,
            largura=DialogoPadrao.PEQUENO,
        )

        corpo = self.corpo


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

        corpo.addWidget(campo_rotulado("Valor inicial (troco)", self.valor))

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

        # Vendedor nao ve o historico (tem o valor de cada fechamento)
        ve_historico = api.usuario_tem_permissao("financeiro.ver")
        if ve_historico:
            corpo.addWidget(titulo_secao("Últimas sessões"))

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

        if ve_historico:
            corpo.addWidget(historico_frame)
            self.carregar_historico()

        corpo.addStretch()

        self.bt_abrir = BotaoSucesso("Abrir Caixa", icone_nome="check")
        self.bt_abrir.setAutoDefault(False)
        self.bt_abrir.clicked.connect(self.confirmar)
        self.bt_cancelar = self.definir_botoes(self.bt_abrir)

        self.ajustar_altura()
        self.valor.setFocus()

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

        # adiado: as linhas recém-adicionadas só aparecem (e contam na
        # medida) no próximo ciclo de eventos
        QTimer.singleShot(0, self.ajustar_altura)

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
