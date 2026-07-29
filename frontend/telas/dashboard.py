from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
)

from services.api import dashboard, me, configuracoes
from widgets.card import Card
from widgets.nav_card import NavCard

DIAS_SEMANA = [
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
]

MESES = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


class Dashboard(QWidget):

    navegar_pdv = Signal()
    navegar_estoque = Signal()
    navegar_caixa = Signal()

    def __init__(self):

        super().__init__()

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:#f4f5f7;")

        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(30, 25, 30, 25)
        layout_principal.setSpacing(20)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()

        config = configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"

        usuario = me()
        nome_usuario = usuario.get("nome") or "Usuário"

        col_esquerda = QVBoxLayout()
        col_esquerda.setSpacing(2)

        self.lbl_loja = QLabel(nome_loja)
        self.lbl_loja.setStyleSheet(
            "background:transparent; font-size:22px; "
            "font-weight:bold; color:#202225;"
        )

        self.lbl_saudacao = QLabel(f"Olá, {nome_usuario}!")
        self.lbl_saudacao.setStyleSheet(
            "background:transparent; font-size:14px; color:gray;"
        )

        col_esquerda.addWidget(self.lbl_loja)
        col_esquerda.addWidget(self.lbl_saudacao)

        self.lbl_relogio = QLabel()
        self.lbl_relogio.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_relogio.setStyleSheet(
            "background:transparent; font-size:14px; color:#444;"
        )

        cabecalho.addLayout(col_esquerda)
        cabecalho.addStretch()
        cabecalho.addWidget(self.lbl_relogio)

        # ======================
        # CARDS DE NAVEGAÇÃO
        # ======================

        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(16)

        self.card_pdv = NavCard(
            "Frente de Caixa",
            "Venda rápida (F3)",
            "#4e6bff",
            "#7b3fe4",
        )

        self.card_estoque = NavCard(
            "Estoque",
            "Gestão de itens",
            "#1fa065",
            "#0d7a4b",
        )

        self.card_caixa = NavCard(
            "Abertura / Fech.",
            "Turno e sessões",
            "#ff9d3f",
            "#ff7a1a",
        )

        self.card_pdv.clicado.connect(self.navegar_pdv.emit)
        self.card_estoque.clicado.connect(self.navegar_estoque.emit)
        self.card_caixa.clicado.connect(self.navegar_caixa.emit)

        nav_layout.addWidget(self.card_pdv)
        nav_layout.addWidget(self.card_estoque)
        nav_layout.addWidget(self.card_caixa)

        # ======================
        # CARDS DE DADOS
        # ======================

        dados_layout = QGridLayout()
        dados_layout.setSpacing(16)

        dados = dashboard()

        self.card_hoje = Card(
            "Hoje",
            f"R$ {dados.get('vendas_hoje', 0):.2f}",
        )

        self.card_qtd_vendas = Card(
            "Vendas",
            dados.get("vendas_hoje_qtd", 0),
        )

        self.card_mes = Card(
            "Mês",
            f"R$ {dados.get('vendas_mes', 0):.2f}",
        )

        dados_layout.addWidget(self.card_hoje, 0, 0)
        dados_layout.addWidget(self.card_qtd_vendas, 0, 1)
        dados_layout.addWidget(self.card_mes, 0, 2)

        layout_principal.addLayout(cabecalho)
        layout_principal.addLayout(nav_layout)
        layout_principal.addLayout(dados_layout)
        layout_principal.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.atualizar_relogio)
        self.timer.start(1000)
        self.atualizar_relogio()

    def atualizar_relogio(self):

        agora = datetime.now()
        dia_semana = DIAS_SEMANA[agora.weekday()]
        mes = MESES[agora.month - 1]

        texto = (
            f"{agora.strftime('%H:%M')}\n"
            f"{dia_semana}, {agora.day} de {mes}"
        )

        self.lbl_relogio.setText(texto)
