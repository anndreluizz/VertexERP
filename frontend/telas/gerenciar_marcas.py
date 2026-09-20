from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QInputDialog,
)

from services.marca_service import (
    listar_marcas,
    criar_marca,
    atualizar_marca,
    excluir_marca,
)
from services.worker import rodar_em_thread

from design import tokens


def _listar_marcas_ativas():
    return [c for c in listar_marcas() if c.get("ativo", True)]


class GerenciarMarcasDialog(QDialog):
    """Mesmo padrao de GerenciarCategoriasDialog/GerenciarCategoriasDespesaDialog
    -- antes desse dialogo, a unica forma de criar uma marca de produto
    era o "+" no cadastro, sem nenhum jeito de corrigir um nome
    digitado errado ou remover uma marca duplicada/nao usada."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.marcas = []
        self._carregando = False

        self.setWindowTitle("Gerenciar Marcas")
        self.resize(480, 480)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Marcas de Produto")
        titulo.setStyleSheet(
            f"background:transparent; font-size:18px; "
            f"font-weight:bold; color:{tokens.TEXTO};"
        )
        layout.addWidget(titulo)

        nova_layout = QHBoxLayout()

        self.novo_nome = QLineEdit()
        self.novo_nome.setPlaceholderText("Nova marca...")
        self.novo_nome.setMinimumHeight(40)
        self.novo_nome.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {tokens.BORDA};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QLineEdit:focus {{
                border: 1px solid {tokens.SECUNDARIA};
            }}
        """)
        self.novo_nome.returnPressed.connect(self.adicionar)

        self.bt_adicionar = QPushButton("+ Adicionar")
        self.bt_adicionar.setAutoDefault(False)
        self.bt_adicionar.setMinimumHeight(40)
        self.bt_adicionar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.SECUNDARIA};
                color:{tokens.TEXTO_CLARO};
                font-weight:bold;
                border-radius:8px;
                padding:0 16px;
            }}
            QPushButton:hover {{
                background:{tokens.SECUNDARIA_HOVER};
            }}
        """)
        self.bt_adicionar.clicked.connect(self.adicionar)

        nova_layout.addWidget(self.novo_nome)
        nova_layout.addWidget(self.bt_adicionar)

        layout.addLayout(nova_layout)

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
                border-radius: 8px;
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
                font-weight: bold;
                padding: 6px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
        """)

        layout.addWidget(self.tabela, stretch=1)

        rodape = QHBoxLayout()

        self.bt_editar = QPushButton("Editar")
        self.bt_editar.setAutoDefault(False)
        self.bt_editar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.PRIMARIA};
                color:{tokens.TEXTO_CLARO};
                font-weight:bold;
                border-radius:8px;
                padding:8px 16px;
            }}
            QPushButton:hover {{
                background:{tokens.PRIMARIA_HOVER};
            }}
        """)
        self.bt_editar.clicked.connect(self.editar)

        self.bt_excluir = QPushButton("Excluir")
        self.bt_excluir.setAutoDefault(False)
        self.bt_excluir.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.ERRO};
                color:{tokens.TEXTO_CLARO};
                font-weight:bold;
                border-radius:8px;
                padding:8px 16px;
            }}
            QPushButton:hover {{
                background:{tokens.ERRO_HOVER};
            }}
        """)
        self.bt_excluir.clicked.connect(self.excluir)

        bt_fechar = QPushButton("Fechar")
        bt_fechar.setAutoDefault(False)
        bt_fechar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.FUNDO};
                color:{tokens.TEXTO};
                border-radius:8px;
                padding:8px 20px;
            }}
            QPushButton:hover {{
                background:{tokens.BORDA};
            }}
        """)
        bt_fechar.clicked.connect(self.accept)

        rodape.addWidget(self.bt_editar)
        rodape.addWidget(self.bt_excluir)
        rodape.addStretch()
        rodape.addWidget(bt_fechar)

        layout.addLayout(rodape)

        self.carregar()

    # ======================================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            _listar_marcas_ativas,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_adicionar.setEnabled(not carregando)
        self.bt_editar.setEnabled(not carregando)
        self.bt_excluir.setEnabled(not carregando)

    def _ao_carregar_sucesso(self, marcas):

        self.marcas = marcas

        self.tabela.setRowCount(len(self.marcas))

        for linha, marca in enumerate(self.marcas):
            self.tabela.setItem(
                linha, 0, QTableWidgetItem(marca.get("nome", ""))
            )

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar as marcas.\n{erro}")

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def _marca_selecionada(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(
                self, "Aviso", "Selecione uma marca."
            )
            return None

        return self.marcas[linha]

    def adicionar(self):

        nome = self.novo_nome.text().strip()

        if not nome:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            criar_marca,
            nome,
            ao_sucesso=self._ao_adicionar_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_adicionar_sucesso(self, response):
        if response.status_code in (200, 201):
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

        marca = self._marca_selecionada()

        if marca is None:
            return

        novo_nome, ok = QInputDialog.getText(
            self,
            "Editar marca",
            "Nome da marca:",
            QLineEdit.Normal,
            marca.get("nome", ""),
        )

        if not ok:
            return

        novo_nome = novo_nome.strip()

        if not novo_nome:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            atualizar_marca,
            marca["id"],
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

        marca = self._marca_selecionada()

        if marca is None:
            return

        resposta = QMessageBox.question(
            self,
            "Excluir marca",
            f"Excluir a marca \"{marca.get('nome')}\"?\n\n"
            "Produtos que já usam essa marca não são alterados "
            "-- ela só deixa de aparecer na lista pra novos cadastros.",
        )

        if resposta != QMessageBox.Yes:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            excluir_marca,
            marca["id"],
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
