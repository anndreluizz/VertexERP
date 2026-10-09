from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QCheckBox,
    QPushButton,
    QScrollArea,
    QWidget,
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
from design.widgets import (
    BotaoPerigo, BotaoSecundario, BotaoSucesso, CampoTexto, DialogoPadrao,
    campo_rotulado, tabela_lista, titulo_secao,
)


def _estilo_permissao():
    """Cada permissão é uma linha inteira clicável que fica destacada
    quando marcada -- o estado aparece de longe, não só no quadradinho."""
    return f"""
        QCheckBox {{
            background:{tokens.CARD}; color:{tokens.TEXTO};
            border:1.5px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
            padding:9px 10px; font-size:{tokens.TAMANHO_BASE}px; spacing:10px;
        }}
        QCheckBox:hover {{ border-color:{tokens.BORDA_FORTE}; }}
        QCheckBox:checked {{
            background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA};
            border-color:{tokens.PRIMARIA}; font-weight:700;
        }}
        QCheckBox::indicator {{
            width:16px; height:16px; border-radius:4px;
            border:1.5px solid {tokens.BORDA_FORTE}; background:{tokens.CARD};
        }}
        QCheckBox::indicator:checked {{
            border:1.5px solid {tokens.PRIMARIA}; background:{tokens.PRIMARIA};
        }}
    """


def _estilo_link():
    return f"""
        QPushButton {{
            background:transparent; border:none; color:{tokens.PRIMARIA};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700; padding:2px 4px;
        }}
        QPushButton:hover {{ text-decoration:underline; }}
    """


class GerenciarPerfisDialog(DialogoPadrao):
    """Perfil = nome + subconjunto do catalogo fixo de permissoes (ver
    app/auth/permissoes.py no backend) -- usuario comum com um perfil
    atribuido ganha so' essas acoes, sem virar admin de verdade (ver
    GerenciarUsuariosDialog pra atribuir um perfil a um usuario)."""

    def __init__(self, parent=None):
        super().__init__(
            "Perfis de Acesso", "Escolha o que cada tipo de funcionário pode fazer",
            "lock", largura=DialogoPadrao.GRANDE, parent=parent,
        )
        self.resize(DialogoPadrao.GRANDE, 700)

        self.perfis = []
        self.permissoes_disponiveis = {}
        self.checkboxes = {}
        self.perfil_selecionado_id = None
        self._carregando = False

        # ---- coluna da esquerda: perfis ----
        col_lista = QVBoxLayout()
        col_lista.setSpacing(10)

        self.bt_novo = BotaoSecundario("Novo perfil", icone_nome="plus")
        self.bt_novo.setAutoDefault(False)
        self.bt_novo.clicked.connect(self.novo)

        col_lista.addWidget(titulo_secao("Perfis"))
        col_lista.addWidget(self.bt_novo)

        self.tabela = tabela_lista(["Nome", "Permissões"])
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tabela.itemSelectionChanged.connect(self._ao_selecionar_linha)
        col_lista.addWidget(self.tabela, 1)

        # ---- coluna da direita: perfil em edição ----
        col_form = QVBoxLayout()
        col_form.setSpacing(12)

        self.lbl_modo = titulo_secao("Novo perfil")
        col_form.addWidget(self.lbl_modo)

        self.nome = CampoTexto("Ex.: Gerente, Caixa, Estoquista...", cor_foco=tokens.PRIMARIA)
        self.nome.returnPressed.connect(self.salvar)
        col_form.addWidget(campo_rotulado("Nome do perfil", self.nome))

        linha_perm = QHBoxLayout()
        linha_perm.setSpacing(6)
        self.lbl_contador = QLabel("Permissões")
        self.lbl_contador.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; color:{tokens.TEXTO_SECUNDARIO};
        """)
        bt_todas = QPushButton("Marcar todas")
        bt_nenhuma = QPushButton("Limpar")
        for bt, marcar in ((bt_todas, True), (bt_nenhuma, False)):
            bt.setCursor(Qt.PointingHandCursor)
            bt.setAutoDefault(False)
            bt.setStyleSheet(_estilo_link())
            bt.clicked.connect(lambda _c=False, m=marcar: self._marcar_todas(m))
        linha_perm.addWidget(self.lbl_contador)
        linha_perm.addStretch()
        linha_perm.addWidget(bt_todas)
        linha_perm.addWidget(bt_nenhuma)
        col_form.addLayout(linha_perm)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        self.painel_permissoes = QWidget()
        self.painel_permissoes.setStyleSheet("background:transparent;")
        self.layout_permissoes = QGridLayout(self.painel_permissoes)
        self.layout_permissoes.setContentsMargins(0, 0, 4, 0)
        self.layout_permissoes.setHorizontalSpacing(8)
        self.layout_permissoes.setVerticalSpacing(8)
        self.layout_permissoes.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.painel_permissoes)
        col_form.addWidget(scroll, 1)

        colunas = QHBoxLayout()
        colunas.setSpacing(24)
        colunas.addLayout(col_lista, 2)
        colunas.addLayout(col_form, 3)
        self.corpo.addLayout(colunas, 1)

        # ---- rodapé: excluir à esquerda; fechar + salvar à direita ----
        self.bt_excluir = BotaoPerigo("Excluir perfil", icone_nome="trash-2")
        self.bt_excluir.setAutoDefault(False)
        self.bt_excluir.clicked.connect(self.excluir)
        self.rodape.addWidget(self.bt_excluir)

        self.bt_salvar = BotaoSucesso("Salvar perfil", icone_nome="check")
        self.bt_salvar.setAutoDefault(False)
        self.bt_salvar.clicked.connect(self.salvar)
        self.definir_botoes(self.bt_salvar, texto_cancelar="Fechar")
        self.bt_cancelar.clicked.disconnect()
        self.bt_cancelar.clicked.connect(self.accept)

        # atalhos: Ctrl+S salva, Ctrl+N novo perfil
        for tecla, acao in (("Ctrl+S", self.salvar), ("Ctrl+N", self.novo)):
            atalho = QShortcut(QKeySequence(tecla), self)
            atalho.activated.connect(acao)

        self._atualizar_modo()
        self.carregar()

    def _marcar_todas(self, marcar):
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(marcar)

    def _atualizar_contador(self):
        total = len(self.checkboxes)
        marcadas = sum(c.isChecked() for c in self.checkboxes.values())
        self.lbl_contador.setText(f"Permissões  ·  {marcadas} de {total} marcadas")

    def _atualizar_modo(self):
        """Título da coluna da direita e botão Excluir conforme está
        criando um perfil novo ou editando um existente."""
        editando = self.perfil_selecionado_id is not None
        lbl = self.lbl_modo.findChild(QLabel)
        if lbl is not None:
            lbl.setText("EDITANDO PERFIL" if editando else "NOVO PERFIL")
        self.bt_excluir.setVisible(editando)

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
        estilo = _estilo_permissao()
        for indice, (chave, rotulo) in enumerate(permissoes.items()):
            checkbox = QCheckBox(rotulo)
            checkbox.setCursor(Qt.PointingHandCursor)
            checkbox.setStyleSheet(estilo)
            checkbox.toggled.connect(self._atualizar_contador)
            self.layout_permissoes.addWidget(checkbox, indice, 0)
            self.checkboxes[chave] = checkbox
        self._atualizar_contador()

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
            total = len(self.permissoes_disponiveis) or len(perfil["permissoes"])
            item_qtd = QTableWidgetItem(f"{len(perfil['permissoes'])} de {total}")
            item_qtd.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tabela.setItem(linha, 1, item_qtd)

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

        self._atualizar_modo()

    def novo(self):
        self.perfil_selecionado_id = None
        self.nome.clear()
        self.tabela.clearSelection()
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)
        self._atualizar_modo()
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
