from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QWidget,
)

from services.plano_conta_service import (
    listar_planos_conta,
    cadastrar_plano_conta,
    atualizar_plano_conta,
    excluir_plano_conta,
)
from services.worker import rodar_em_thread
from services import api

from design import tokens
from design.icons import icone
from design.widgets import (
    BotaoPerigo, BotaoPrimario, BotaoSecundario, BotaoSucesso, CampoTexto,
    DialogoPadrao, campo_rotulado, estilo_lista, pedir_texto,
)

_ROTULO_TIPO = {"RECEITA": "Receitas", "DESPESA": "Despesas"}



def _cor_tipo(tipo):
    return tokens.SECUNDARIA if tipo == "RECEITA" else tokens.ERRO


class NovaContaRaizDialog(DialogoPadrao):
    """Tipo (Despesa/Receita) + nome numa tela só -- antes eram duas
    caixinhas seguidas do Windows (QInputDialog.getItem e getText)."""

    def __init__(self, tipo="DESPESA", parent=None):

        super().__init__(
            "Nova conta raiz", "Grupo principal do plano de contas", "plus",
            tokens.SECUNDARIA, tokens.SUCESSO_CLARO,
            largura=DialogoPadrao.PEQUENO, parent=parent,
        )

        self.tipo = tipo

        bloco_tipo = QWidget()
        bloco_tipo.setStyleSheet("background:transparent;")
        linha_tipo = QHBoxLayout(bloco_tipo)
        linha_tipo.setContentsMargins(0, 0, 0, 0)
        linha_tipo.setSpacing(10)
        self.botoes_tipo = {}
        for valor, rotulo, icone_nome in (
            ("DESPESA", "Despesa", "arrow-down"), ("RECEITA", "Receita", "arrow-up"),
        ):
            bt = QPushButton(rotulo)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setAutoDefault(False)
            bt.setMinimumHeight(46)
            bt.clicked.connect(lambda _c=False, v=valor: self._escolher_tipo(v))
            bt.icone_nome = icone_nome
            linha_tipo.addWidget(bt, 1)
            self.botoes_tipo[valor] = bt

        self.corpo.addWidget(campo_rotulado("Tipo", bloco_tipo))

        self.nome = CampoTexto("Ex.: Despesas fixas, Vendas...")
        self.nome.returnPressed.connect(self.confirmar)
        self.corpo.addWidget(campo_rotulado("Nome", self.nome))
        self.corpo.addStretch()

        bt_criar = BotaoSucesso("Criar conta", icone_nome="check")
        bt_criar.setAutoDefault(False)
        bt_criar.clicked.connect(self.confirmar)
        self.definir_botoes(bt_criar)

        self._escolher_tipo(tipo)
        self.ajustar_altura()
        self.nome.setFocus()

    def _escolher_tipo(self, tipo):

        self.tipo = tipo
        for valor, bt in self.botoes_tipo.items():
            cor = QColor(_cor_tipo(valor))
            rgb = f"{cor.red()}, {cor.green()}, {cor.blue()}"
            if valor == tipo:
                texto = tokens.FUNDO if tokens.ESCURO_ATIVO else "#FFFFFF"
                estilo = f"background:{cor.name()}; color:{texto}; border:1.5px solid {cor.name()};"
            else:
                texto = cor.name()
                estilo = (
                    f"background:rgba({rgb}, 0.08); color:{texto}; "
                    f"border:1.5px solid rgba({rgb}, 0.35);"
                )
            bt.setStyleSheet(f"""
                QPushButton {{ {estilo} border-radius:{tokens.RADIUS_SM}px;
                    font-weight:700; font-size:{tokens.TAMANHO_MD}px; }}
            """)
            bt.setIcon(icone(bt.icone_nome, cor=texto, tamanho=16))

    def confirmar(self):
        if not self.nome.text().strip():
            self.nome.setFocus()
            return
        self.accept()


class GerenciarPlanoContasDialog(DialogoPadrao):
    """Arvore de duas raizes fixas (Receitas/Despesas, nao sao contas de
    verdade -- so agrupam visualmente) com as contas de PlanoConta
    aninhadas por conta_pai_id. Selecionar uma conta real habilita
    editar/excluir/nova subconta; selecionar um cabecalho ou nada so
    deixa "Nova conta raiz" disponivel."""

    def __init__(self, parent=None):
        super().__init__(
            "Plano de Contas", "Receitas e despesas organizadas em grupos e subcontas",
            "trending-up", largura=DialogoPadrao.MEDIO, parent=parent,
        )
        self.resize(DialogoPadrao.MEDIO, 680)

        self.contas = []
        self._carregando = False

        # ---- barra de criação (em cima da árvore) ----
        barra = QHBoxLayout()
        barra.setSpacing(10)

        self.bt_nova_raiz = BotaoSucesso("Nova conta raiz", icone_nome="plus")
        self.bt_nova_raiz.setAutoDefault(False)
        self.bt_nova_raiz.clicked.connect(self.nova_raiz)

        self.bt_nova_sub = BotaoSecundario("Nova subconta", icone_nome="plus")
        self.bt_nova_sub.setAutoDefault(False)
        self.bt_nova_sub.clicked.connect(self.nova_subconta)

        barra.addWidget(self.bt_nova_raiz)
        barra.addWidget(self.bt_nova_sub)
        barra.addStretch()
        self.corpo.addLayout(barra)

        self.arvore = QTreeWidget()
        self.arvore.setHeaderHidden(True)
        self.arvore.setIndentation(26)
        self.arvore.setStyleSheet(estilo_lista() + """
            QTreeWidget::item { min-height:40px; }
        """)
        self.arvore.itemDoubleClicked.connect(self._ao_duplo_clique)
        self.corpo.addWidget(self.arvore, stretch=1)

        self.lbl_dica = QLabel(
            "Selecione uma conta pra criar subcontas dentro dela  ·  "
            "F2 ou duplo clique edita  ·  Del exclui"
        )
        self.lbl_dica.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        self.corpo.addWidget(self.lbl_dica)

        # ---- rodapé: editar/excluir à esquerda, fechar à direita ----
        self.bt_editar = BotaoSecundario("Editar", icone_nome="edit-2")
        self.bt_editar.setAutoDefault(False)
        self.bt_editar.clicked.connect(self.editar)

        self.bt_excluir = BotaoPerigo("Excluir", icone_nome="trash-2")
        self.bt_excluir.setAutoDefault(False)
        self.bt_excluir.clicked.connect(self.excluir)

        bt_fechar = BotaoPrimario("Fechar")
        bt_fechar.setAutoDefault(False)
        bt_fechar.setMinimumWidth(140)
        bt_fechar.clicked.connect(self.accept)

        self.rodape.addWidget(self.bt_editar)
        self.rodape.addWidget(self.bt_excluir)
        self.rodape.addStretch()
        self.rodape.addWidget(bt_fechar)

        for tecla, acao in ((Qt.Key_F2, self.editar), (Qt.Key_Delete, self._excluir_por_tecla)):
            atalho = QShortcut(QKeySequence(tecla), self)
            atalho.activated.connect(acao)

        self.arvore.currentItemChanged.connect(self._ao_selecionar)
        self._ao_selecionar(None, None)

        if not api.usuario_tem_permissao("plano_contas.excluir"):
            self.bt_excluir.setVisible(False)

        self.carregar()

    # ======================================
    # CARREGAR / MONTAR ARVORE
    # ======================================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            listar_planos_conta,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_nova_raiz.setEnabled(not carregando)
        if carregando:
            self.bt_nova_sub.setEnabled(False)
            self.bt_editar.setEnabled(False)
            self.bt_excluir.setEnabled(False)

    def _ao_mutacao_finalizada(self):
        if not self._carregando:
            self._definir_controles_carregando(False)

    def _ao_carregar_sucesso(self, contas):

        self.contas = contas
        self.arvore.clear()

        cabecalhos = {}
        for tipo, rotulo in _ROTULO_TIPO.items():
            item = QTreeWidgetItem([rotulo.upper()])
            item.setData(0, Qt.UserRole, None)
            item.setData(0, Qt.UserRole + 1, tipo)
            fonte = item.font(0)
            fonte.setBold(True)
            item.setFont(0, fonte)
            item.setForeground(0, QBrush(QColor(_cor_tipo(tipo))))
            self.arvore.addTopLevelItem(item)
            cabecalhos[tipo] = item

        itens_por_id = {}
        for conta in contas:
            texto = conta["nome"]
            if conta.get("codigo"):
                texto = f"{conta['codigo']} — {texto}"
            item = QTreeWidgetItem([texto])
            item.setData(0, Qt.UserRole, conta)
            itens_por_id[conta["id"]] = item

        for conta in contas:
            item = itens_por_id[conta["id"]]
            pai_id = conta.get("conta_pai_id")
            if pai_id and pai_id in itens_por_id:
                itens_por_id[pai_id].addChild(item)
            else:
                cabecalhos[conta["tipo"]].addChild(item)

        for conta in contas:
            if conta.get("conta_pai_id") not in itens_por_id:
                item = itens_por_id[conta["id"]]
                fonte = item.font(0)
                fonte.setBold(True)
                item.setFont(0, fonte)

        self.arvore.expandAll()

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar o plano de contas.\n{erro}"
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)
        self._ao_selecionar(self.arvore.currentItem(), None)

    # ======================================
    # SELECAO
    # ======================================

    def _conta_selecionada(self):
        item = self.arvore.currentItem()
        return item.data(0, Qt.UserRole) if item else None

    def _tipo_selecionado(self):
        """Tipo da conta ou do cabeçalho (Receitas/Despesas) selecionado."""
        item = self.arvore.currentItem()
        if item is None:
            return "DESPESA"
        conta = item.data(0, Qt.UserRole)
        return conta["tipo"] if conta else (item.data(0, Qt.UserRole + 1) or "DESPESA")

    def _ao_duplo_clique(self, item, _coluna):
        # duplo clique no cabeçalho (Receitas/Despesas) cria conta raiz
        # daquele tipo; numa conta, edita
        if item.data(0, Qt.UserRole) is None:
            self.nova_raiz()
        else:
            self.editar()

    def _excluir_por_tecla(self):
        if self.bt_excluir.isVisible() and self.bt_excluir.isEnabled():
            self.excluir()

    def _ao_selecionar(self, atual, anterior):
        conta = atual.data(0, Qt.UserRole) if atual else None
        self.bt_nova_sub.setEnabled(conta is not None)
        self.bt_editar.setEnabled(conta is not None)
        self.bt_excluir.setEnabled(conta is not None)

    # ======================================
    # NOVA CONTA RAIZ / SUBCONTA
    # ======================================

    def nova_raiz(self):

        dialogo = NovaContaRaizDialog(self._tipo_selecionado(), parent=self)
        if dialogo.exec() != QDialog.Accepted:
            return

        self._salvar_nova(dialogo.nome.text().strip(), dialogo.tipo, None)

    def nova_subconta(self):

        conta_pai = self._conta_selecionada()
        if conta_pai is None:
            return

        nome, ok = pedir_texto(
            self, "Nova subconta", "Nome da subconta",
            icone_nome="plus", subtitulo=f"Dentro de \"{conta_pai['nome']}\"",
            texto_botao="Criar subconta",
        )
        if not ok or not nome.strip():
            return

        self._salvar_nova(nome.strip(), conta_pai["tipo"], conta_pai["id"])

    def _salvar_nova(self, nome, tipo, conta_pai_id):

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            cadastrar_plano_conta,
            nome,
            tipo,
            conta_pai_id,
            ao_sucesso=self._ao_mutacao_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    # ======================================
    # EDITAR / EXCLUIR
    # ======================================

    def editar(self):

        conta = self._conta_selecionada()
        if conta is None:
            return

        novo_nome, ok = pedir_texto(
            self, "Editar conta", "Nome da conta", conta["nome"],
        )
        if not ok or not novo_nome.strip():
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            atualizar_plano_conta,
            conta["id"],
            novo_nome.strip(),
            conta["tipo"],
            conta.get("conta_pai_id"),
            conta.get("codigo"),
            True,
            ao_sucesso=self._ao_mutacao_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def excluir(self):

        conta = self._conta_selecionada()
        if conta is None:
            return

        resposta = QMessageBox.question(
            self, "Excluir conta",
            f"Excluir \"{conta['nome']}\"? Contas com subcontas ativas "
            "não podem ser excluídas.",
        )
        if resposta != QMessageBox.Yes:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            excluir_plano_conta,
            conta["id"],
            ao_sucesso=self._ao_mutacao_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_mutacao_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutacao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))
