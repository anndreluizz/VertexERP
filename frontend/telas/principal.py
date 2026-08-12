from telas.dashboard import Dashboard
from telas.pdv import PDV
from telas.caixa import Caixa
from telas.produtos import Produtos
from telas.clientes import Clientes
from telas.fornecedores import Fornecedores
from telas.compras import Compras
from telas.vendas import Vendas
from telas.ajuste_estoque import AjusteEstoque
from telas.relatorios import Relatorios
from telas.configuracoes import Configuracoes
from telas.contas_pagar import ContasPagar
from services.api import usuario_e_admin
from services.configuracao_service import (
    buscar_configuracoes,
    buscar_logo_bytes,
)

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
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


class PilhaDePaginas(QStackedWidget):
    """QStackedWidget comum dimensiona a janela pelo MAIOR conteúdo entre
    TODAS as páginas cadastradas, não só a que está visível — uma tela
    larga (ex.: Relatórios, com filtros + gráficos lado a lado) inflava a
    janela inteira mesmo com o usuário em outra página, tipo o
    Dashboard. Aqui o tamanho considera só a página atual."""

    def sizeHint(self):
        atual = self.currentWidget()
        return atual.sizeHint() if atual else super().sizeHint()

    def minimumSizeHint(self):
        atual = self.currentWidget()
        return (
            atual.minimumSizeHint()
            if atual
            else super().minimumSizeHint()
        )


class PrincipalWindow(QMainWindow):

    def _ajustar_tamanho_a_tela(self):
        # Calcular pixel na mão (resize + setMaximumSize) deu problema nos
        # dois sentidos dependendo da tela/escala do Windows de cada PC —
        # ora abria maior que a tela, ora travava pequena sem deixar
        # aumentar. Deixa o próprio Windows decidir o que cabe: maximiza
        # (preenche a área útil, sem cobrir a barra de tarefas) e não
        # define nenhum tamanho máximo, então o usuário ainda pode
        # restaurar e redimensionar a janela livremente se quiser.
        self.setWindowState(Qt.WindowMaximized)

    def __init__(self):
        super().__init__()

        self._ajustar_tamanho_a_tela()

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

        config = buscar_configuracoes()
        logo_bytes = buscar_logo_bytes()

        self.setWindowTitle(config.get("nome_loja") or "Vertex ERP")

        if logo_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(logo_bytes)
            titulo = QLabel()
            titulo.setPixmap(
                pixmap.scaledToWidth(140, Qt.SmoothTransformation)
            )
        else:
            titulo = QLabel(config.get("nome_loja") or "VERTEX ERP")

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
        self.bt_contas_pagar = QPushButton("📄 Contas a Pagar")
        self.bt_ajuste_estoque = QPushButton("🔧 Ajuste Estoque")
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
            self.bt_contas_pagar,
            self.bt_ajuste_estoque,
            self.bt_relatorios,
            self.bt_config,
        ]

        for botao in botoes:
            menu_layout.addWidget(botao)

        menu_layout.addStretch()

        # ======================
        # ÁREA CENTRAL
        # ======================

        self.paginas = PilhaDePaginas()

        self.dashboard = Dashboard()
        self.pdv = PDV()
        self.produtos = Produtos()
        self.clientes = Clientes()

        self.fornecedores = Fornecedores()

        self.compras = Compras()

        self.vendas = Vendas()

        self.caixa = Caixa()

        self.contas_pagar = ContasPagar()

        self.ajuste_estoque = AjusteEstoque()

        self.relatorios = Relatorios()

        self.config = Configuracoes()

        self.paginas.addWidget(self.dashboard)
        self.paginas.addWidget(self.pdv)
        self.paginas.addWidget(self.produtos)
        self.paginas.addWidget(self.clientes)
        self.paginas.addWidget(self.fornecedores)
        self.paginas.addWidget(self.compras)
        self.paginas.addWidget(self.vendas)
        self.paginas.addWidget(self.caixa)
        self.paginas.addWidget(self.contas_pagar)
        self.paginas.addWidget(self.ajuste_estoque)
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

        self.bt_contas_pagar.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.contas_pagar)
        )

        self.bt_ajuste_estoque.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.ajuste_estoque)
        )

        self.bt_relatorios.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.relatorios)
        )

        self.bt_config.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.config)
        )

        # Configurações da loja/PIX/usuários é coisa de admin — operador
        # nem vê o menu.
        if not usuario_e_admin():
            self.bt_config.setVisible(False)