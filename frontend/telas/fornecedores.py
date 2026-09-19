from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import BotaoPrimario, BotaoSecundario
from services.fornecedor_service import listar_fornecedores, excluir_fornecedor
from services.worker import rodar_em_thread
from telas.cadastro_fornecedor import CadastroFornecedorDialog
from telas.importar_nfe import ImportarNFeDialog


class Fornecedores(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.fornecedores = []
        self._carregando = False

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(12)

        self.bt_voltar = QPushButton()
        self.bt_voltar.setFixedSize(36, 36)
        self.bt_voltar.setCursor(Qt.PointingHandCursor)
        self.bt_voltar.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        self.bt_voltar.setToolTip("Voltar")
        self.bt_voltar.setAccessibleName("Voltar")
        self.bt_voltar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        icone_titulo = QLabel()
        icone_titulo.setFixedSize(36, 36)
        icone_titulo.setAlignment(Qt.AlignCenter)
        icone_titulo.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_SM}px;
        """)
        icone_titulo.setPixmap(icone_pixmap("truck", cor=tokens.PRIMARIA, tamanho=18))

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Fornecedores")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            "Cadastre fornecedores e importe notas fiscais (NF-e) pra "
            "dar entrada em produtos e estoque em lote."
        )
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        self.bt_importar_nfe = BotaoSecundario("Importar NF-e", icone_nome="arrow-up")
        self.bt_importar_nfe.clicked.connect(self.abrir_importar_nfe)

        self.bt_novo = BotaoPrimario("Novo Fornecedor", icone_nome="plus")
        self.bt_novo.clicked.connect(self.novo_fornecedor)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addWidget(icone_titulo)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_importar_nfe)
        cabecalho.addWidget(self.bt_novo)

        layout.addLayout(cabecalho)

        # ======================
        # TABELA
        # ======================

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(5)
        self.tabela.setHorizontalHeaderLabels(
            ["Razão Social", "Nome Fantasia", "CNPJ", "Margem", "Ativo"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
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
                font-weight: bold;
                padding: 6px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
        """)

        layout.addWidget(self.tabela, stretch=1)

        rodape = QHBoxLayout()

        self.bt_editar = BotaoSecundario("Editar")
        self.bt_editar.clicked.connect(self.editar_selecionado)

        self.bt_excluir = BotaoSecundario("Excluir")
        self.bt_excluir.clicked.connect(self.excluir_selecionado)

        rodape.addWidget(self.bt_editar)
        rodape.addWidget(self.bt_excluir)
        rodape.addStretch()

        layout.addLayout(rodape)

    # ======================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            listar_fornecedores,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_novo.setEnabled(not carregando)
        self.bt_importar_nfe.setEnabled(not carregando)
        self.bt_editar.setEnabled(not carregando)
        self.bt_excluir.setEnabled(not carregando)

    def _ao_carregar_sucesso(self, fornecedores):

        self.fornecedores = fornecedores
        self.tabela.setRowCount(len(fornecedores))

        for linha, f in enumerate(fornecedores):
            self.tabela.setItem(linha, 0, QTableWidgetItem(f.get("razao_social", "")))
            self.tabela.setItem(linha, 1, QTableWidgetItem(f.get("nome_fantasia") or ""))
            self.tabela.setItem(linha, 2, QTableWidgetItem(f.get("cnpj", "")))
            self.tabela.setItem(
                linha, 3, QTableWidgetItem(f"{float(f.get('margem_padrao') or 0):.2f}%")
            )
            self.tabela.setItem(
                linha, 4, QTableWidgetItem("Sim" if f.get("ativo", True) else "Não")
            )

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar os fornecedores.\n{erro}"
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def _fornecedor_selecionado(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um fornecedor.")
            return None

        return self.fornecedores[linha]

    def novo_fornecedor(self):
        dialog = CadastroFornecedorDialog(parent=self)
        if dialog.exec():
            self.carregar()

    def editar_selecionado(self):

        fornecedor = self._fornecedor_selecionado()
        if fornecedor is None:
            return

        dialog = CadastroFornecedorDialog(fornecedor=fornecedor, parent=self)
        if dialog.exec():
            self.carregar()

    def excluir_selecionado(self):

        fornecedor = self._fornecedor_selecionado()
        if fornecedor is None:
            return

        resposta = QMessageBox.question(
            self,
            "Excluir fornecedor",
            f"Excluir o fornecedor \"{fornecedor.get('razao_social')}\"?\n\n"
            "O histórico de compras dele é mantido -- ele só deixa de "
            "aparecer nas listas pra novas compras/importações.",
        )

        if resposta != QMessageBox.Yes:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            excluir_fornecedor,
            fornecedor["id"],
            ao_sucesso=self._ao_excluir_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _ao_excluir_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def abrir_importar_nfe(self):
        dialog = ImportarNFeDialog(parent=self)
        if dialog.exec():
            self.carregar()
