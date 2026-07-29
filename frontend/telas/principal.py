from telas.dashboard import Dashboard
from telas.pdv import PDV
from telas.caixa import Caixa
from telas.produtos import Produtos
from telas.clientes import Clientes
from telas.relatorios import Relatorios
from telas.contas_pagar import ContasPagar
from telas.visao_geral import VisaoGeral
from telas.configuracoes import Configuracoes
from telas.caixa_bloqueado import CaixaBloqueadoDialog
from telas.abrir_caixa import AbrirCaixaWindow

from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QStackedWidget,
    QDialog,
    QMessageBox,
)

from services.caixa_service import caixa_aberto, abrir_caixa


class PrincipalWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Vertex ERP")
        self.resize(1400, 800)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ======================
        # MENU LATERAL
        # ======================

        menu = QFrame()
        menu.setFixedWidth(230)
        menu.setStyleSheet("""
            QFrame{
                background:#202225;
            }

            QPushButton{
                color:white;
                background:transparent;
                border:none;
                text-align:left;
                padding:15px;
                font-size:14px;
            }

            QPushButton:hover{
                background:#2d3136;
            }

            QLabel{
                color:white;
                font-size:20px;
                font-weight:bold;
                padding:20px;
            }
        """)

        menu_layout = QVBoxLayout(menu)

        titulo = QLabel("VERTEX ERP")
        titulo.setAlignment(Qt.AlignCenter)

        menu_layout.addWidget(titulo)

        self.bt_dashboard = QPushButton("🏠 Início")
        self.bt_produtos = QPushButton("📦 Produtos")
        self.bt_clientes = QPushButton("👥 Clientes")
        self.bt_caixa = QPushButton("💰 Caixa")
        self.bt_contas_pagar = QPushButton("📉 Contas a Pagar")
        self.bt_visao_geral = QPushButton("📈 Visão Geral")
        self.bt_relatorios = QPushButton("📊 Relatórios")
        self.bt_config = QPushButton("⚙ Configurações")

        botoes = [
            self.bt_dashboard,
            self.bt_produtos,
            self.bt_clientes,
            self.bt_caixa,
            self.bt_contas_pagar,
            self.bt_visao_geral,
            self.bt_relatorios,
            self.bt_config,
        ]

        for botao in botoes:
            menu_layout.addWidget(botao)

        menu_layout.addStretch()

        # ======================
        # ÁREA CENTRAL
        # ======================

        self.paginas = QStackedWidget()

        self.dashboard = Dashboard()
        self.pdv = PDV()
        self.produtos = Produtos()

        self.clientes = Clientes()

        self.caixa = Caixa()

        self.contas_pagar = ContasPagar()

        self.visao_geral = VisaoGeral()

        self.relatorios = Relatorios()

        self.config = Configuracoes()

        self.paginas.addWidget(self.dashboard)
        self.paginas.addWidget(self.pdv)
        self.paginas.addWidget(self.produtos)
        self.paginas.addWidget(self.clientes)
        self.paginas.addWidget(self.caixa)
        self.paginas.addWidget(self.contas_pagar)
        self.paginas.addWidget(self.visao_geral)
        self.paginas.addWidget(self.relatorios)
        self.paginas.addWidget(self.config)

        layout.addWidget(menu)
        layout.addWidget(self.paginas)

        # ======================
        # EVENTOS
        # ======================

        self.bt_dashboard.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.dashboard)
        )

        self.bt_produtos.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.produtos)
        )

        self.bt_clientes.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.clientes)
        )

        self.bt_caixa.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.caixa)
        )

        self.bt_contas_pagar.clicked.connect(
            self.ir_para_contas_pagar
        )

        self.bt_visao_geral.clicked.connect(self.ir_para_visao_geral)

        self.bt_relatorios.clicked.connect(self.ir_para_relatorios)

        self.bt_config.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.config)
        )

        self.dashboard.navegar_pdv.connect(self.ir_para_pdv)

        self.dashboard.navegar_estoque.connect(
            lambda: self.paginas.setCurrentWidget(self.produtos)
        )

        self.dashboard.navegar_caixa.connect(
            lambda: self.paginas.setCurrentWidget(self.caixa)
        )

        self.pdv.voltar.connect(
            lambda: self.paginas.setCurrentWidget(self.dashboard)
        )

        self.produtos.voltar.connect(
            lambda: self.paginas.setCurrentWidget(self.dashboard)
        )

        self.clientes.voltar.connect(
            lambda: self.paginas.setCurrentWidget(self.dashboard)
        )

        self.config.voltar.connect(
            lambda: self.paginas.setCurrentWidget(self.dashboard)
        )

        self.relatorios.voltar.connect(
            lambda: self.paginas.setCurrentWidget(self.dashboard)
        )

        self.contas_pagar.voltar.connect(
            lambda: self.paginas.setCurrentWidget(self.dashboard)
        )

        self.visao_geral.voltar.connect(
            lambda: self.paginas.setCurrentWidget(self.dashboard)
        )

        self.paginas.setCurrentWidget(self.dashboard)

        # ======================
        # ATALHOS
        # ======================

        self.atalho_pdv = QShortcut(QKeySequence("F3"), self)
        self.atalho_pdv.activated.connect(self.atalho_f3)

    def atalho_f3(self):

        if self.paginas.currentWidget() is self.pdv:
            self.pdv.finalizar_venda()
        else:
            self.ir_para_pdv()

    def ir_para_pdv(self):

        if caixa_aberto() is not None:
            self.paginas.setCurrentWidget(self.pdv)
            return

        bloqueado = CaixaBloqueadoDialog(self)

        if bloqueado.exec() != QDialog.Accepted:
            return

        if not bloqueado.abrir_solicitado:
            return

        janela = AbrirCaixaWindow()

        if janela.exec() != QDialog.Accepted:
            return

        response = abrir_caixa(janela.saldo)

        if response.status_code != 200:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.warning(self, "Erro", erro)
            return

        self.caixa.carregar()
        self.paginas.setCurrentWidget(self.pdv)

    def ir_para_relatorios(self):

        self.relatorios.carregar()
        self.paginas.setCurrentWidget(self.relatorios)

    def ir_para_contas_pagar(self):

        self.contas_pagar.carregar()
        self.paginas.setCurrentWidget(self.contas_pagar)

    def ir_para_visao_geral(self):

        self.visao_geral.carregar()
        self.paginas.setCurrentWidget(self.visao_geral)