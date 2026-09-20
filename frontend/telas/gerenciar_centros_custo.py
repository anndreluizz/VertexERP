from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QInputDialog,
)

from services.centro_custo_service import (
    listar_centros_custo,
    cadastrar_centro_custo,
    atualizar_centro_custo,
    excluir_centro_custo,
)
from services.worker import rodar_em_thread
from services import api

from design import tokens
from design.widgets import BotaoPerigo, BotaoPrimario, BotaoSecundario, BotaoSucesso, CampoTexto


class GerenciarCentrosCustoDialog(QDialog):
    """Mesmo padrao de GerenciarCategoriasDespesaDialog -- centro de
    custo agrupa despesas por area/departamento (ver
    ContaPagar.centro_custo)."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.centros = []
        self._carregando = False

        self.setWindowTitle("Gerenciar Centros de Custo")
        self.resize(480, 480)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Centros de Custo")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        layout.addWidget(titulo)

        novo_layout = QHBoxLayout()

        self.novo_nome = CampoTexto(
            "Novo centro de custo...", cor_foco=tokens.SECUNDARIA
        )
        self.novo_nome.returnPressed.connect(self.adicionar)

        self.bt_adicionar = BotaoSucesso("Adicionar", icone_nome="plus")
        self.bt_adicionar.setAutoDefault(False)
        self.bt_adicionar.clicked.connect(self.adicionar)

        novo_layout.addWidget(self.novo_nome)
        novo_layout.addWidget(self.bt_adicionar)

        layout.addLayout(novo_layout)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(1)
        self.tabela.setHorizontalHeaderLabels(["Nome"])
        self.tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela.verticalHeader().setDefaultSectionSize(40)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                alternate-background-color: {tokens.FUNDO};
            }}
            QTableWidget::item:selected {{
                background: {tokens.PRIMARIA};
                color: {tokens.TEXTO_CLARO};
            }}
            QHeaderView::section {{
                background: {tokens.FUNDO};
                color: {tokens.TEXTO};
                font-weight: 700;
                padding: 8px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
        """)

        layout.addWidget(self.tabela, stretch=1)

        rodape = QHBoxLayout()

        self.bt_editar = BotaoPrimario("Editar", icone_nome="edit-2")
        self.bt_editar.setAutoDefault(False)
        self.bt_editar.clicked.connect(self.editar)

        self.bt_excluir = BotaoPerigo("Excluir", icone_nome="trash-2")
        self.bt_excluir.setAutoDefault(False)
        self.bt_excluir.clicked.connect(self.excluir)

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.setAutoDefault(False)
        bt_fechar.clicked.connect(self.accept)

        rodape.addWidget(self.bt_editar)
        rodape.addWidget(self.bt_excluir)
        rodape.addStretch()
        rodape.addWidget(bt_fechar)

        layout.addLayout(rodape)

        if not api.usuario_tem_permissao("centros_custo.excluir"):
            self.bt_excluir.setVisible(False)

        self.carregar()

    # ======================================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            listar_centros_custo,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_adicionar.setEnabled(not carregando)
        self.bt_editar.setEnabled(not carregando)
        self.bt_excluir.setEnabled(not carregando)

    def _ao_carregar_sucesso(self, centros):

        self.centros = centros

        self.tabela.setRowCount(len(self.centros))

        for linha, centro in enumerate(self.centros):
            self.tabela.setItem(
                linha, 0, QTableWidgetItem(centro.get("nome", ""))
            )

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar os centros de custo.\n{erro}")

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def _centro_selecionado(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(
                self, "Aviso", "Selecione um centro de custo."
            )
            return None

        return self.centros[linha]

    def adicionar(self):

        nome = self.novo_nome.text().strip()

        if not nome:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            cadastrar_centro_custo,
            nome,
            ao_sucesso=self._ao_adicionar_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_adicionar_sucesso(self, response):
        if response.status_code == 200:
            self.novo_nome.clear()
            self.carregar()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutacao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutacao_finalizada(self):
        if not self._carregando:
            self._definir_controles_carregando(False)

    def editar(self):

        centro = self._centro_selecionado()

        if centro is None:
            return

        novo_nome, ok = QInputDialog.getText(
            self,
            "Editar centro de custo",
            "Nome do centro de custo:",
            QLineEdit.Normal,
            centro.get("nome", ""),
        )

        if not ok:
            return

        novo_nome = novo_nome.strip()

        if not novo_nome:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            atualizar_centro_custo,
            centro["id"],
            novo_nome,
            ao_sucesso=self._ao_editar_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_editar_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def excluir(self):

        centro = self._centro_selecionado()

        if centro is None:
            return

        resposta = QMessageBox.question(
            self,
            "Excluir centro de custo",
            f"Excluir o centro de custo \"{centro.get('nome')}\"?",
        )

        if resposta != QMessageBox.Yes:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            excluir_centro_custo,
            centro["id"],
            ao_sucesso=self._ao_excluir_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_excluir_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
