from telas.dashboard import Dashboard
from telas.pdv import PDV
from telas.vendas import Vendas
from telas.caixa import Caixa
from telas.produtos import Produtos
from telas.ajuste_estoque import AjusteEstoque
from telas.transferencia_estoque import TransferenciaEstoque
from telas.contagem_estoque import ContagemEstoque
from telas.clientes import Clientes
from telas.fornecedores import Fornecedores
from telas.relatorios import Relatorios
from telas.inteligencia_negocios import InteligenciaNegocios
from telas.contas_pagar import ContasPagar
from telas.conciliacao_bancaria import ConciliacaoBancaria
from telas.visao_geral import VisaoGeral
from telas.configuracoes import Configuracoes
from telas.caixa_bloqueado import CaixaBloqueadoDialog
from telas.abrir_caixa import AbrirCaixaWindow
from telas.trocar_senha import TrocarSenhaDialog

import os
import sys

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QDialog,
    QMessageBox,
    QFrame,
    QLabel,
    QPushButton,
)

from design import tokens
from design.icons import icone
from design.sidebar import Sidebar
from design.header import Header
from design.janela import pintar_barra_titulo
from design.widgets import BotaoSecundario, PilhaPaginas
from services import api, backup_service
from services.caixa_service import caixa_aberto, abrir_caixa
from services.preferencias_service import salvar_tema_escuro
from services.worker import rodar_em_thread
from utils.formatacao import formatar_moeda

# intervalo da checagem de "sem conexao com o servidor" em segundo
# plano (ver Header.definir_online) -- nao precisa ser rapido, e so'
# um indicador; 20s equilibra perceber a queda logo sem gerar trafego
# nenhum digno de nota.
_INTERVALO_CONEXAO_MS = 20_000

# checagem do status do backup (so' pra admin, ver FaixaAvisoBackup) --
# a primeira espera o launcher terminar o backup que ele dispara logo
# ao abrir, senao numa loja que ficou fechada no domingo o aviso de
# "backup atrasado" piscaria toda segunda de manha a' toa.
_ATRASO_PRIMEIRA_CHECAGEM_BACKUP_MS = 60_000
_INTERVALO_BACKUP_MS = 30 * 60_000


class FaixaAvisoBackup(QFrame):
    """Faixa amarela abaixo do Header, so' pra admin, quando o backup
    nao esta protegendo a loja (issue #4: o backup ficou quebrado por
    semanas sem ninguem ver, e a loja perdeu os dados quando o
    PC-Servidor foi formatado). A mensagem vem pronta do backend
    (BackupService.alerta)."""

    ver_backups = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("faixaAvisoBackup")
        self.setStyleSheet(f"""
            QFrame#faixaAvisoBackup {{
                background: {tokens.ALERTA_CLARO};
                border: none;
                border-bottom: 1px solid {tokens.ALERTA};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 12, 8)
        layout.setSpacing(12)

        self.lbl_mensagem = QLabel()
        self.lbl_mensagem.setWordWrap(True)
        self.lbl_mensagem.setStyleSheet(f"""
            background: transparent; border: none;
            color: {tokens.ALERTA_TEXTO};
            font-size: {tokens.TAMANHO_SM}px; font-weight: 600;
        """)
        layout.addWidget(self.lbl_mensagem, stretch=1)

        bt_ver = BotaoSecundario("Ver backups")
        bt_ver.clicked.connect(self.ver_backups)
        layout.addWidget(bt_ver)

        bt_fechar = QPushButton()
        bt_fechar.setIcon(icone("x", cor=tokens.ALERTA_TEXTO, tamanho=16))
        bt_fechar.setToolTip("Esconder até a próxima checagem")
        bt_fechar.setFixedSize(28, 28)
        bt_fechar.setCursor(Qt.PointingHandCursor)
        bt_fechar.setStyleSheet("background: transparent; border: none;")
        bt_fechar.clicked.connect(self.hide)
        layout.addWidget(bt_fechar)

        self.setVisible(False)

    def definir_status(self, dados):
        alerta = dados.get("alerta") if isinstance(dados, dict) else None
        self.lbl_mensagem.setText(f"⚠ Backup: {alerta}" if alerta else "")
        self.setVisible(bool(alerta))


# (chave, ícone lucide, rótulo) — única fonte de verdade pra montar tanto
# os itens da sidebar quanto o título mostrado no header.
ITENS_MENU = [
    ("dashboard", "home", "Início"),
    ("pdv", "shopping-cart", "PDV"),
    ("vendas", "file-text", "Vendas"),
    ("produtos", "package", "Produtos"),
    ("ajuste_estoque", "refresh-cw", "Ajuste de Estoque"),
    ("transferencia_estoque", "store", "Transferência entre Lojas"),
    ("contagem_estoque", "check", "Contagem de Inventário"),
    ("clientes", "users", "Clientes"),
    ("fornecedores", "truck", "Fornecedores"),
    ("caixa", "wallet", "Caixa"),
    ("contas_pagar", "file-text", "Contas a Pagar"),
    ("conciliacao_bancaria", "credit-card", "Conciliação Bancária"),
    ("visao_geral", "trending-up", "Visão Geral"),
    ("relatorios", "bar-chart-2", "Relatórios"),
    ("inteligencia", "lightbulb", "Inteligência de Negócios"),
    ("config", "settings", "Configurações"),
]


class PrincipalWindow(QMainWindow):

    def __init__(self, info_usuario=None, config=None):
        super().__init__()

        self.setWindowTitle("Vertex ERP")
        self.resize(1400, 800)
        # abre maximizada, igual a tela de login -- quem cria a janela
        # so' chama show(), e esse estado ja vale pra ele
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet(f"QMainWindow {{ background: {tokens.FUNDO}; }}")
        # barra de título do Windows na cor do menu lateral (era a branca
        # padrão, destoando do menu azul-escuro logo abaixo)
        pintar_barra_titulo(self, tokens.SIDEBAR, tokens.TEXTO_CLARO)

        # info_usuario/config podem vir ja' prontos de quem chamou (ver
        # telas/login.py e telas/cadastro_inicial.py, que buscam isso
        # assincrono ANTES de construir a janela) -- None aqui so'
        # acontece em app.py, no caminho de retomar sessao/primeiro
        # acesso, que roda antes do event loop do Qt existir (nao da'
        # pra usar rodar_em_thread la', nao tem fila de eventos rodando
        # ainda pra entregar o resultado); nesses casos cai de volta
        # pro fetch sincrono de sempre.
        if info_usuario is None:
            info_usuario = api.me()
        if config is None:
            config = api.configuracoes()

        nome_usuario = info_usuario.get("nome") or "Usuário"
        cargo = "Administrador" if info_usuario.get("admin") else "Operador"

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

        self.faixa_backup = FaixaAvisoBackup()
        self.faixa_backup.ver_backups.connect(self._abrir_aba_backup)
        layout_central.addWidget(self.faixa_backup)

        self.paginas = PilhaPaginas()
        layout_central.addWidget(self.paginas, stretch=1)

        self.dashboard = Dashboard(usuario_id=info_usuario.get("id"))
        self.pdv = PDV()
        self.vendas = Vendas()
        self.produtos = Produtos()
        self.ajuste_estoque = AjusteEstoque()
        self.transferencia_estoque = TransferenciaEstoque()
        self.contagem_estoque = ContagemEstoque()

        self.clientes = Clientes()

        self.fornecedores = Fornecedores()

        self.caixa = Caixa()

        self.contas_pagar = ContasPagar()

        self.conciliacao_bancaria = ConciliacaoBancaria()

        self.visao_geral = VisaoGeral()

        self.relatorios = Relatorios()

        self.inteligencia = InteligenciaNegocios()

        self.config = Configuracoes()

        self.paginas.addWidget(self.dashboard)
        self.paginas.addWidget(self.pdv)
        self.paginas.addWidget(self.vendas)
        self.paginas.addWidget(self.produtos)
        self.paginas.addWidget(self.ajuste_estoque)
        self.paginas.addWidget(self.transferencia_estoque)
        self.paginas.addWidget(self.contagem_estoque)
        self.paginas.addWidget(self.clientes)
        self.paginas.addWidget(self.fornecedores)
        self.paginas.addWidget(self.caixa)
        self.paginas.addWidget(self.contas_pagar)
        self.paginas.addWidget(self.conciliacao_bancaria)
        self.paginas.addWidget(self.visao_geral)
        self.paginas.addWidget(self.relatorios)
        self.paginas.addWidget(self.inteligencia)
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

        self.vendas.voltar.connect(
            lambda: self._exibir_pagina("dashboard", self.dashboard)
        )
        self.vendas.troca_iniciada.connect(self._iniciar_troca)

        self.clientes.voltar.connect(
            lambda: self._exibir_pagina("dashboard", self.dashboard)
        )

        self.fornecedores.voltar.connect(
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

        # ======================
        # STATUS DE CONEXAO -- checagem leve em segundo plano, so pra
        # acender/apagar o aviso do Header (ver design/header.py); cada
        # tela ja trata falha de rede na hora H sozinha, isso e so um
        # indicador de fundo pra avisar cedo quando a rede cai no meio
        # da sessao (ex.: filial perdendo conexao com o servidor da
        # matriz).
        # ======================

        self._timer_conexao = QTimer(self)
        self._timer_conexao.timeout.connect(self._checar_conexao)
        self._timer_conexao.start(_INTERVALO_CONEXAO_MS)

        # ======================
        # STATUS DO BACKUP -- so' admin ve (e so' admin pode chamar
        # GET /backup/, que e' get_current_admin)
        # ======================

        if info_usuario.get("admin"):
            self._timer_backup = QTimer(self)
            self._timer_backup.timeout.connect(self._checar_backup)
            self._timer_backup.start(_INTERVALO_BACKUP_MS)
            QTimer.singleShot(
                _ATRASO_PRIMEIRA_CHECAGEM_BACKUP_MS, self._checar_backup
            )

    def _checar_backup(self):
        # sem ao_erro de proposito: servidor fora do ar ja' tem o aviso
        # proprio no Header, nao precisa de um segundo aqui
        rodar_em_thread(
            self,
            backup_service.listar_backups,
            ao_sucesso=self.faixa_backup.definir_status,
        )

    def _abrir_aba_backup(self):
        self._exibir_pagina("config", self.config)
        # forca recarregar -- a aba pode ter sido aberta antes do
        # problema aparecer, com o historico antigo ainda em cache
        self.config._backups_carregados = False
        self.config._selecionar_aba(8)

    def _checar_conexao(self):
        rodar_em_thread(
            self,
            api.servidor_online,
            ao_sucesso=self.header.definir_online,
        )

    def _exibir_pagina(self, chave, pagina):

        if chave == "dashboard":
            self.dashboard.carregar()
        elif chave == "clientes":
            self.clientes.carregar()
        elif chave == "vendas":
            self.vendas.carregar()
        elif chave == "fornecedores":
            self.fornecedores.carregar()
        elif chave == "ajuste_estoque":
            self.ajuste_estoque.carregar()
        elif chave == "transferencia_estoque":
            self.transferencia_estoque.carregar()
        elif chave == "contagem_estoque":
            self.contagem_estoque.carregar()
        elif chave == "conciliacao_bancaria":
            self.conciliacao_bancaria.carregar()

        self.paginas.setCurrentWidget(pagina)
        self.header.definir_titulo(self._titulos.get(chave, ""))
        self.sidebar.selecionar(chave)

    def _navegar(self, chave):

        despachantes = {
            "pdv": self.ir_para_pdv,
            "contas_pagar": self.ir_para_contas_pagar,
            "visao_geral": self.ir_para_visao_geral,
            "relatorios": self.ir_para_relatorios,
            "inteligencia": self.ir_para_inteligencia,
        }

        if chave in despachantes:
            despachantes[chave]()
            return

        paginas = {
            "dashboard": self.dashboard,
            "produtos": self.produtos,
            "vendas": self.vendas,
            "ajuste_estoque": self.ajuste_estoque,
            "transferencia_estoque": self.transferencia_estoque,
            "contagem_estoque": self.contagem_estoque,
            "conciliacao_bancaria": self.conciliacao_bancaria,
            "clientes": self.clientes,
            "fornecedores": self.fornecedores,
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

    def _iniciar_troca(self, credito, cliente):
        """Devolução da troca registrada na tela de Vendas -- abre o PDV
        com o valor como crédito (ver PDV.iniciar_troca)."""

        self.ir_para_pdv()

        if self.paginas.currentWidget() is self.pdv:
            self.pdv.iniciar_troca(credito, cliente)
        else:
            QMessageBox.information(
                self,
                "Troca",
                "A devolução foi registrada, mas o PDV não abriu. Devolva "
                f"{formatar_moeda(credito)} em dinheiro para a cliente.",
            )

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

    def ir_para_inteligencia(self):

        self.inteligencia.carregar()
        self._exibir_pagina("inteligencia", self.inteligencia)

    def ir_para_contas_pagar(self):

        self.contas_pagar.carregar()
        self._exibir_pagina("contas_pagar", self.contas_pagar)

    def ir_para_visao_geral(self):

        self.visao_geral.carregar()
        self._exibir_pagina("visao_geral", self.visao_geral)