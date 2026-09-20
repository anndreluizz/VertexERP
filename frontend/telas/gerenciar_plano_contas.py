from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QInputDialog,
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
from design.widgets import BotaoPerigo, BotaoPrimario, BotaoSecundario, BotaoSucesso

_ROTULO_TIPO = {"RECEITA": "Receitas", "DESPESA": "Despesas"}


class GerenciarPlanoContasDialog(QDialog):
    """Arvore de duas raizes fixas (Receitas/Despesas, nao sao contas de
    verdade -- so agrupam visualmente) com as contas de PlanoConta
    aninhadas por conta_pai_id. Selecionar uma conta real habilita
    editar/excluir/nova subconta; selecionar um cabecalho ou nada so
    deixa "Nova conta raiz" disponivel."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.contas = []
        self._carregando = False

        self.setWindowTitle("Plano de Contas")
        self.resize(560, 560)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Plano de Contas")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        layout.addWidget(titulo)

        self.arvore = QTreeWidget()
        self.arvore.setHeaderHidden(True)
        self.arvore.setStyleSheet(f"""
            QTreeWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QTreeWidget::item {{ padding: 4px; }}
            QTreeWidget::item:selected {{
                background: {tokens.PRIMARIA};
                color: {tokens.TEXTO_CLARO};
            }}
        """)
        layout.addWidget(self.arvore, stretch=1)

        rodape = QHBoxLayout()

        self.bt_nova_raiz = BotaoSucesso("Nova conta raiz", icone_nome="plus")
        self.bt_nova_raiz.setAutoDefault(False)
        self.bt_nova_raiz.clicked.connect(self.nova_raiz)

        self.bt_nova_sub = BotaoSecundario("Nova subconta", icone_nome="plus")
        self.bt_nova_sub.setAutoDefault(False)
        self.bt_nova_sub.clicked.connect(self.nova_subconta)

        self.bt_editar = BotaoPrimario("Editar", icone_nome="edit-2")
        self.bt_editar.setAutoDefault(False)
        self.bt_editar.clicked.connect(self.editar)

        self.bt_excluir = BotaoPerigo("Excluir", icone_nome="trash-2")
        self.bt_excluir.setAutoDefault(False)
        self.bt_excluir.clicked.connect(self.excluir)

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.setAutoDefault(False)
        bt_fechar.clicked.connect(self.accept)

        rodape.addWidget(self.bt_nova_raiz)
        rodape.addWidget(self.bt_nova_sub)
        rodape.addWidget(self.bt_editar)
        rodape.addWidget(self.bt_excluir)
        rodape.addStretch()
        rodape.addWidget(bt_fechar)

        layout.addLayout(rodape)

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
            item = QTreeWidgetItem([rotulo])
            item.setData(0, Qt.UserRole, None)
            fonte = item.font(0)
            fonte.setBold(True)
            item.setFont(0, fonte)
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

    def _ao_selecionar(self, atual, anterior):
        conta = atual.data(0, Qt.UserRole) if atual else None
        self.bt_nova_sub.setEnabled(conta is not None)
        self.bt_editar.setEnabled(conta is not None)
        self.bt_excluir.setEnabled(conta is not None)

    # ======================================
    # NOVA CONTA RAIZ / SUBCONTA
    # ======================================

    def nova_raiz(self):

        tipo, ok = QInputDialog.getItem(
            self, "Nova conta raiz", "Tipo:",
            ["DESPESA", "RECEITA"], 0, False,
        )
        if not ok:
            return

        nome, ok = QInputDialog.getText(self, "Nova conta raiz", "Nome:")
        if not ok or not nome.strip():
            return

        self._salvar_nova(nome.strip(), tipo, None)

    def nova_subconta(self):

        conta_pai = self._conta_selecionada()
        if conta_pai is None:
            return

        nome, ok = QInputDialog.getText(
            self, "Nova subconta",
            f"Nome (dentro de \"{conta_pai['nome']}\"):",
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

        novo_nome, ok = QInputDialog.getText(
            self, "Editar conta", "Nome:",
            QLineEdit.Normal, conta["nome"],
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
