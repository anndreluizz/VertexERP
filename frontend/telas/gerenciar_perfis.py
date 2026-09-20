from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QCheckBox,
    QScrollArea,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from services.perfil_service import (
    listar_perfis,
    listar_permissoes_disponiveis,
    cadastrar_perfil,
    atualizar_perfil,
    excluir_perfil,
)
from services.worker import rodar_em_thread

from design import tokens
from design.widgets import BotaoPerigo, BotaoPrimario, BotaoSecundario, BotaoSucesso, CampoTexto


class GerenciarPerfisDialog(QDialog):
    """Perfil = nome + subconjunto do catalogo fixo de permissoes (ver
    app/auth/permissoes.py no backend) -- usuario comum com um perfil
    atribuido ganha so' essas acoes, sem virar admin de verdade (ver
    GerenciarUsuariosDialog pra atribuir um perfil a um usuario)."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.perfis = []
        self.permissoes_disponiveis = {}
        self.checkboxes = {}
        self.perfil_selecionado_id = None
        self._carregando = False

        self.setWindowTitle("Gerenciar Perfis")
        self.resize(620, 600)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Perfis de Acesso")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        layout.addWidget(titulo)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(2)
        self.tabela.setHorizontalHeaderLabels(["Nome", "Permissões"])
        self.tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela.verticalHeader().setDefaultSectionSize(36)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setMaximumHeight(160)
        self.tabela.itemSelectionChanged.connect(self._ao_selecionar_linha)
        layout.addWidget(self.tabela)

        layout.addWidget(self._rotulo("Nome do perfil"))

        self.nome = CampoTexto("Ex.: Gerente, Supervisor...", cor_foco=tokens.PRIMARIA)
        layout.addWidget(self.nome)

        layout.addWidget(self._rotulo("Permissões"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {tokens.BORDA}; "
            f"border-radius: {tokens.RADIUS_SM}px; }}"
        )

        self.painel_permissoes = QWidget()
        self.layout_permissoes = QVBoxLayout(self.painel_permissoes)
        self.layout_permissoes.setContentsMargins(12, 10, 12, 10)
        self.layout_permissoes.setSpacing(6)
        scroll.setWidget(self.painel_permissoes)

        layout.addWidget(scroll, stretch=1)

        rodape = QHBoxLayout()
        rodape.setSpacing(8)

        self.bt_novo = BotaoSecundario("Novo")
        self.bt_novo.setAutoDefault(False)
        self.bt_novo.clicked.connect(self.novo)
        rodape.addWidget(self.bt_novo)

        self.bt_salvar = BotaoSucesso("Salvar")
        self.bt_salvar.setAutoDefault(False)
        self.bt_salvar.clicked.connect(self.salvar)
        rodape.addWidget(self.bt_salvar)

        self.bt_excluir = BotaoPerigo("Excluir")
        self.bt_excluir.setAutoDefault(False)
        self.bt_excluir.clicked.connect(self.excluir)
        rodape.addWidget(self.bt_excluir)

        rodape.addStretch()

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.setAutoDefault(False)
        bt_fechar.clicked.connect(self.accept)
        rodape.addWidget(bt_fechar)

        layout.addLayout(rodape)

        self.carregar()

    def _rotulo(self, texto):
        lbl = QLabel(texto)
        lbl.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SECUNDARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; font-weight:700;"
        )
        return lbl

    # ======================================
    # CARREGAR
    # ======================================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            listar_permissoes_disponiveis,
            ao_sucesso=self._ao_carregar_permissoes_sucesso,
            ao_erro=self._ao_carregar_erro,
        )

    def _ao_carregar_permissoes_sucesso(self, permissoes):

        self.permissoes_disponiveis = permissoes

        while self.layout_permissoes.count():
            item = self.layout_permissoes.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.checkboxes = {}
        for chave, rotulo in permissoes.items():
            checkbox = QCheckBox(rotulo)
            checkbox.setStyleSheet(
                f"background:transparent; color:{tokens.TEXTO};"
            )
            self.layout_permissoes.addWidget(checkbox)
            self.checkboxes[chave] = checkbox

        rodar_em_thread(
            self,
            listar_perfis,
            ao_sucesso=self._ao_carregar_perfis_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _ao_carregar_perfis_sucesso(self, perfis):

        self.perfis = perfis
        self.tabela.setRowCount(len(perfis))

        for linha, perfil in enumerate(perfis):
            self.tabela.setItem(linha, 0, QTableWidgetItem(perfil["nome"]))
            self.tabela.setItem(
                linha, 1, QTableWidgetItem(str(len(perfil["permissoes"])))
            )

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar os perfis.\n{erro}"
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_novo.setEnabled(not carregando)
        self.bt_salvar.setEnabled(not carregando)
        self.bt_excluir.setEnabled(not carregando)

    # ======================================
    # SELECIONAR / NOVO
    # ======================================

    def _ao_selecionar_linha(self):

        linha = self.tabela.currentRow()
        if linha < 0:
            return

        perfil = self.perfis[linha]
        self.perfil_selecionado_id = perfil["id"]
        self.nome.setText(perfil["nome"])

        for chave, checkbox in self.checkboxes.items():
            checkbox.setChecked(chave in perfil["permissoes"])

    def novo(self):
        self.perfil_selecionado_id = None
        self.nome.clear()
        self.tabela.clearSelection()
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)
        self.nome.setFocus()

    # ======================================
    # SALVAR / EXCLUIR
    # ======================================

    def salvar(self):

        nome = self.nome.text().strip()
        if not nome:
            QMessageBox.warning(self, "Aviso", "Informe o nome do perfil.")
            return

        permissoes = [
            chave for chave, checkbox in self.checkboxes.items()
            if checkbox.isChecked()
        ]

        self._definir_controles_carregando(True)

        if self.perfil_selecionado_id is None:
            rodar_em_thread(
                self,
                cadastrar_perfil,
                nome,
                permissoes,
                ao_sucesso=self._ao_salvar_sucesso,
                ao_erro=self._ao_mutacao_erro,
                ao_finalizar=self._ao_carregar_finalizado,
            )
        else:
            rodar_em_thread(
                self,
                atualizar_perfil,
                self.perfil_selecionado_id,
                nome,
                permissoes,
                ao_sucesso=self._ao_salvar_sucesso,
                ao_erro=self._ao_mutacao_erro,
                ao_finalizar=self._ao_carregar_finalizado,
            )

    def _ao_salvar_sucesso(self, response):
        if response.status_code == 200:
            self.novo()
            self.carregar()
        else:
            self._exibir_erro(response)

    def excluir(self):

        if self.perfil_selecionado_id is None:
            QMessageBox.warning(self, "Aviso", "Selecione um perfil.")
            return

        resposta = QMessageBox.question(
            self, "Excluir perfil",
            f"Excluir o perfil \"{self.nome.text()}\"?",
        )
        if resposta != QMessageBox.Yes:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            excluir_perfil,
            self.perfil_selecionado_id,
            ao_sucesso=self._ao_salvar_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _ao_mutacao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _exibir_erro(self, response):
        try:
            erro = response.json().get("detail") or str(response.json())
        except Exception:
            erro = response.text
        QMessageBox.critical(self, "Erro", str(erro))
