from telas.dashboard import Dashboard
from telas.pdv import PDV
from telas.caixa import Caixa
from telas.produtos import Produtos

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QStackedWidget,
)


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

        self.bt_dashboard = QPushButton("🏠 Dashboard")
        self.bt_pdv = QPushButton("🛒 PDV")
        self.bt_produtos = QPushButton("📦 Produtos")
        self.bt_clientes = QPushButton("👥 Clientes")
        self.bt_fornecedores = QPushButton("🚚 Fornecedores")
        self.bt_compras = QPushButton("📥 Compras")
        self.bt_vendas = QPushButton("🧾 Vendas")
        self.bt_caixa = QPushButton("💰 Caixa")
        self.bt_relatorios = QPushButton("📊 Relatórios")
        self.bt_config = QPushButton("⚙ Configurações")

        botoes = [
            self.bt_dashboard,
            self.bt_pdv,
            self.bt_produtos,
            self.bt_clientes,
            self.bt_fornecedores,
            self.bt_compras,
            self.bt_vendas,
            self.bt_caixa,
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

        self.clientes = QLabel("Clientes")
        self.clientes.setAlignment(Qt.AlignCenter)

        self.fornecedores = QLabel("Fornecedores")
        self.fornecedores.setAlignment(Qt.AlignCenter)

        self.compras = QLabel("Compras")
        self.compras.setAlignment(Qt.AlignCenter)

        self.vendas = QLabel("Vendas")
        self.vendas.setAlignment(Qt.AlignCenter)

        self.caixa = Caixa()

        self.relatorios = QLabel("Relatórios")
        self.relatorios.setAlignment(Qt.AlignCenter)

        self.config = QLabel("Configurações")
        self.config.setAlignment(Qt.AlignCenter)

        self.paginas.addWidget(self.dashboard)
        self.paginas.addWidget(self.pdv)
        self.paginas.addWidget(self.produtos)
        self.paginas.addWidget(self.clientes)
        self.paginas.addWidget(self.fornecedores)
        self.paginas.addWidget(self.compras)
        self.paginas.addWidget(self.vendas)
        self.paginas.addWidget(self.caixa)
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

        self.bt_pdv.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.pdv)
        )

        self.bt_produtos.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.produtos)
        )

        self.bt_clientes.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.clientes)
        )

        self.bt_fornecedores.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.fornecedores)
        )

        self.bt_compras.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.compras)
        )

        self.bt_vendas.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.vendas)
        )

        self.bt_caixa.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.caixa)
        )

        self.bt_relatorios.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.relatorios)
        )

        self.bt_config.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.config)
        )