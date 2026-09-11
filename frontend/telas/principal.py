from telas.dashboard import Dashboard
from telas.pdv import PDV
from telas.caixa import Caixa
from telas.produtos import Produtos
from telas.ajuste_estoque import AjusteEstoque
from telas.clientes import Clientes
from telas.relatorios import Relatorios
from telas.contas_pagar import ContasPagar
from telas.visao_geral import VisaoGeral
from telas.configuracoes import Configuracoes
from telas.caixa_bloqueado import CaixaBloqueadoDialog
from telas.abrir_caixa import AbrirCaixaWindow
from telas.trocar_senha import TrocarSenhaDialog

import os
import sys

from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QStackedWidget,
    QDialog,
    QMessageBox,
)

from design import tokens
from design.sidebar import Sidebar
from design.header import Header
from services import api
from services.caixa_service import caixa_aberto, abrir_caixa
from services.preferencias_service import salvar_tema_escuro


# (chave, ícone lucide, rótulo) — única fonte de verdade pra montar tanto
# os itens da sidebar quanto o título mostrado no header.
ITENS_MENU = [
    ("dashboard", "home", "Início"),
    ("pdv", "shopping-cart", "PDV"),
    ("produtos", "package", "Produtos"),
    ("ajuste_estoque", "refresh-cw", "Ajuste de Estoque"),
    ("clientes", "users", "Clientes"),
    ("caixa", "wallet", "Caixa"),
    ("contas_pagar", "file-text", "Contas a Pagar"),
    ("visao_geral", "trending-up", "Visão Geral"),
    ("relatorios", "bar-chart-2", "Relatórios"),
    ("config", "settings", "Configurações"),
]


class PrincipalWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Vertex ERP")
        self.resize(1400, 800)
        self.setStyleSheet(f"QMainWindow {{ background: {tokens.FUNDO}; }}")

        info_usuario = api.me()
        nome_usuario = info_usuario.get("nome") or "Usuário"
        cargo = "Administrador" if info_usuario.get("admin") else "Operador"

        config = api.configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"

        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ======================
        # MENU LATERAL
        # ======================

        self.sidebar = Sidebar(nome_loja, nome_usuario, cargo)

        self._titulos = {chave: titulo for chave, _, titulo in ITENS_MENU}

        for chave, icone_nome, titulo in ITENS_MENU:
            self.sidebar.adicionar_item(chave, icone_nome, titulo)

        self.sidebar.item_clicado.connect(self._navegar)

        layout.addWidget(self.sidebar)

        # ======================
        # ÁREA CENTRAL (header + páginas)
        # ======================

        area_central = QWidget()
        layout_central = QVBoxLayout(area_central)
        layout_central.setContentsMargins(0, 0, 0, 0)
        layout_central.setSpacing(0)

        self.header = Header(
            nome_loja, nome_usuario, cargo,
            admin=info_usuario.get("admin", False),
        )
        self.header.solicitou_logout.connect(self._fazer_logout)
        self.header.solicitou_trocar_senha.connect(self._abrir_trocar_senha)
        self.header.tema_alternado.connect(self._alternar_tema)
        layout_central.addWidget(self.header)

        self.paginas = QStackedWidget()
        layout_central.addWidget(self.paginas, stretch=1)

        self.dashboard = Dashboard()
        self.pdv = PDV()
        self.produtos = Produtos()
        self.ajuste_estoque = AjusteEstoque()

        self.clientes = Clientes()

        self.caixa = Caixa()

        self.contas_pagar = ContasPagar()

        self.visao_geral = VisaoGeral()

        self.relatorios = Relatorios()

        self.config = Configuracoes()

        self.paginas.addWidget(self.dashboard)
        self.paginas.addWidget(self.pdv)
        self.paginas.addWidget(self.produtos)
        self.paginas.addWidget(self.ajuste_estoque)
        self.paginas.addWidget(self.clientes)
        self.paginas.addWidget(self.caixa)
        self.paginas.addWidget(self.contas_pagar)
        self.paginas.addWidget(self.visao_geral)
        self.paginas.addWidget(self.relatorios)
        self.paginas.addWidget(self.config)

        layout.addWidget(area_central, stretch=1)

        # ======================
        # EVENTOS
        # ======================

        self.dashboard.navegar_pdv.connect(self.ir_para_pdv)

        self.dashboard.navegar_estoque.connect(
            lambda: self._exibir_pagina("produtos", self.produtos)
        )

        self.dashboard.navegar_caixa.connect(
            lambda: self._exibir_pagina("caixa", self.caixa)
        )

        self.dashboard.navegar_relatorios.connect(self.ir_para_relatorios)

        self.pdv.voltar.connect(
            lambda: self._exibir_pagina("dashboard", self.dashboard)
        )

        self.produtos.voltar.connect(
            lambda: self._exibir_pagina("dashboard", self.dashboard)
        )

        self.clientes.voltar.connect(
            lambda: self._exibir_pagina("dashboard", self.dashboard)
        )

        self.config.voltar.connect(
            lambda: self._exibir_pagina("dashboard", self.dashboard)
        )

        self.config.loja_atualizada.connect(self.sidebar.definir_nome_loja)

        self.relatorios.voltar.connect(
            lambda: self._exibir_pagina("dashboard", self.dashboard)
        )

        self.contas_pagar.voltar.connect(
            lambda: self._exibir_pagina("dashboard", self.dashboard)
        )

        self.visao_geral.voltar.connect(
            lambda: self._exibir_pagina("dashboard", self.dashboard)
        )

        self._exibir_pagina("dashboard", self.dashboard)

        # ======================
        # ATALHOS
        # ======================

        self.atalho_pdv = QShortcut(QKeySequence("F3"), self)
        self.atalho_pdv.activated.connect(self.atalho_f3)

    def _exibir_pagina(self, chave, pagina):

        if chave == "dashboard":
            self.dashboard.carregar()
        elif chave == "clientes":
            self.clientes.carregar()
        elif chave == "ajuste_estoque":
            self.ajuste_estoque.carregar()

        self.paginas.setCurrentWidget(pagina)
        self.header.definir_titulo(self._titulos.get(chave, ""))
        self.sidebar.selecionar(chave)

    def _navegar(self, chave):

        despachantes = {
            "pdv": self.ir_para_pdv,
            "contas_pagar": self.ir_para_contas_pagar,
            "visao_geral": self.ir_para_visao_geral,
            "relatorios": self.ir_para_relatorios,
        }

        if chave in despachantes:
            despachantes[chave]()
            return

        paginas = {
            "dashboard": self.dashboard,
            "produtos": self.produtos,
            "ajuste_estoque": self.ajuste_estoque,
            "clientes": self.clientes,
            "caixa": self.caixa,
            "config": self.config,
        }

        self._exibir_pagina(chave, paginas[chave])

    def _fazer_logout(self):

        resposta = QMessageBox.question(
            self,
            "Sair",
            "Deseja realmente encerrar a sessão?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if resposta != QMessageBox.Yes:
            return

        api.logout()

        from telas.login import LoginWindow

        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()

    def _abrir_trocar_senha(self):

        dialogo = TrocarSenhaDialog(parent=self)
        dialogo.exec()

    def _alternar_tema(self, escuro):

        # a paleta so e' lida uma vez, no arranque (ver
        # design.tokens.aplicar via app.py) -- toda tela deste
        # processo ja foi construida com as cores antigas, entao so
        # salvar a preferencia nao muda nada visualmente ate reiniciar
        salvar_tema_escuro(escuro)

        resposta = QMessageBox.question(
            self,
            "Reiniciar o Vertex ERP",
            "O tema só é aplicado depois de reiniciar o programa.\n\n"
            "Reiniciar agora?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if resposta == QMessageBox.Yes:
            self._reiniciar_app()

    def _reiniciar_app(self):

        QApplication.instance().quit()

        # os.execv troca o processo atual pelo mesmo comando de novo --
        # forma padrao de "reiniciar" um app Python sem depender de um
        # processo externo pra relancar. Empacotado (--frozen),
        # sys.executable JA e' o VertexERP-Frontend.exe, entao chamar
        # ele sozinho basta; em modo dev, sys.executable e' o
        # interpretador python -- precisa passar o caminho de app.py
        # (sys.argv[0]) como argumento, senao o processo novo abre o
        # python sem nenhum script pra rodar.
        if getattr(sys, "frozen", False):
            comando = [sys.executable] + sys.argv[1:]
        else:
            comando = [sys.executable, sys.argv[0]] + sys.argv[1:]

        os.execv(sys.executable, comando)

    def atalho_f3(self):

        if self.paginas.currentWidget() is self.pdv:
            self.pdv.finalizar_venda()
        else:
            self.ir_para_pdv()

    def ir_para_pdv(self):

        if caixa_aberto() is not None:
            self._exibir_pagina("pdv", self.pdv)
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
        self._exibir_pagina("pdv", self.pdv)

    def ir_para_relatorios(self):

        self.relatorios.carregar()
        self._exibir_pagina("relatorios", self.relatorios)

    def ir_para_contas_pagar(self):

        self.contas_pagar.carregar()
        self._exibir_pagina("contas_pagar", self.contas_pagar)

    def ir_para_visao_geral(self):

        self.visao_geral.carregar()
        self._exibir_pagina("visao_geral", self.visao_geral)