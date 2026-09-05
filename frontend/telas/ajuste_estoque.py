from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QMessageBox,
    QDialog,
    QTableWidgetItem,
)

from services.produto_service import listar_produtos
from services.estoque_service import listar_movimentos, ajustar_estoque
from widgets.dialogs.pesquisa_window import PesquisaWindow
from widgets.tables.standard_table import StandardTable
from design import tokens


def _estilo_campo():
    return f"""
        QLineEdit, QComboBox {{
            border: 1px solid {tokens.BORDA};
            border-radius: {tokens.RADIUS_SM}px;
            padding: 0 10px;
            background: {tokens.CARD};
            color: {tokens.TEXTO};
        }}
        QLineEdit:focus, QComboBox:focus {{
            border: 1px solid {tokens.PRIMARIA};
        }}
    """


def _estilo_rotulo():
    return (
        f"background:transparent; color:{tokens.TEXTO_SECUNDARIO}; "
        f"font-size:{tokens.TAMANHO_XS}px; font-weight:700;"
    )


class AjusteEstoque(QWidget):

    def __init__(self):
        super().__init__()

        self.produto_id = None

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        titulo = QLabel("Ajuste de Estoque")
        titulo.setStyleSheet(
            f"background:transparent; font-size:{tokens.TAMANHO_XL}px; "
            f"font-weight:800; color:{tokens.TEXTO};"
        )
        layout.addWidget(titulo)

        subtitulo = QLabel(
            "Registre entradas e saídas manuais com motivo — cada "
            "ajuste fica no histórico abaixo, com data e produto."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(
            f"background:transparent; font-size:{tokens.TAMANHO_SM}px; "
            f"color:{tokens.TEXTO_TERCIARIO};"
        )
        layout.addWidget(subtitulo)

        # ==========================================
        # PRODUTO
        # ==========================================
        col_produto = QVBoxLayout()
        col_produto.setSpacing(4)

        lbl_produto = QLabel("PRODUTO")
        lbl_produto.setStyleSheet(_estilo_rotulo())
        col_produto.addWidget(lbl_produto)

        produto_layout = QHBoxLayout()
        produto_layout.setSpacing(8)

        self.produto = QLineEdit()
        self.produto.setReadOnly(True)
        self.produto.setPlaceholderText("Selecione um produto...")
        self.produto.setMinimumHeight(38)
        self.produto.setStyleSheet(_estilo_campo())

        self.bt_produto = QPushButton("Pesquisar")
        self.bt_produto.setMinimumHeight(38)
        self.bt_produto.setCursor(Qt.PointingHandCursor)
        self.bt_produto.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.FUNDO};
                color:{tokens.TEXTO};
                border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
                padding:0 16px;
            }}
            QPushButton:hover {{
                background:{tokens.BORDA};
            }}
        """)

        produto_layout.addWidget(self.produto, stretch=1)
        produto_layout.addWidget(self.bt_produto)

        col_produto.addLayout(produto_layout)
        layout.addLayout(col_produto)

        # ==========================================
        # TIPO / QUANTIDADE / MOTIVO
        # ==========================================
        dados_layout = QHBoxLayout()
        dados_layout.setSpacing(12)

        col_tipo = QVBoxLayout()
        col_tipo.setSpacing(4)
        lbl_tipo = QLabel("TIPO")
        lbl_tipo.setStyleSheet(_estilo_rotulo())
        col_tipo.addWidget(lbl_tipo)

        self.tipo = QComboBox()
        self.tipo.addItems(["Entrada", "Saída"])
        self.tipo.setMinimumHeight(38)
        self.tipo.setStyleSheet(_estilo_campo())
        col_tipo.addWidget(self.tipo)
        dados_layout.addLayout(col_tipo)

        col_quantidade = QVBoxLayout()
        col_quantidade.setSpacing(4)
        lbl_quantidade = QLabel("QUANTIDADE")
        lbl_quantidade.setStyleSheet(_estilo_rotulo())
        col_quantidade.addWidget(lbl_quantidade)

        self.quantidade = QLineEdit()
        self.quantidade.setPlaceholderText("0")
        self.quantidade.setMaximumWidth(120)
        self.quantidade.setMinimumHeight(38)
        self.quantidade.setStyleSheet(_estilo_campo())
        col_quantidade.addWidget(self.quantidade)
        dados_layout.addLayout(col_quantidade)

        col_motivo = QVBoxLayout()
        col_motivo.setSpacing(4)
        lbl_motivo = QLabel("MOTIVO")
        lbl_motivo.setStyleSheet(_estilo_rotulo())
        col_motivo.addWidget(lbl_motivo)

        self.motivo = QLineEdit()
        self.motivo.setPlaceholderText("Ex.: inventário, quebra, correção...")
        self.motivo.setMinimumHeight(38)
        self.motivo.setStyleSheet(_estilo_campo())
        col_motivo.addWidget(self.motivo)
        dados_layout.addLayout(col_motivo, stretch=1)

        col_botao = QVBoxLayout()
        col_botao.setSpacing(4)
        col_botao.addWidget(QLabel(""))  # alinha o botao com os campos

        self.bt_registrar = QPushButton("Registrar Ajuste")
        self.bt_registrar.setMinimumHeight(38)
        self.bt_registrar.setCursor(Qt.PointingHandCursor)
        self.bt_registrar.setStyleSheet(f"""
            QPushButton{{
                background:{tokens.SECUNDARIA};
                color:{tokens.TEXTO_CLARO};
                font-weight:bold;
                border-radius:{tokens.RADIUS_SM}px;
                padding:0 18px;
            }}
            QPushButton:hover{{
                background:{tokens.SECUNDARIA_HOVER};
            }}
        """)
        col_botao.addWidget(self.bt_registrar)
        dados_layout.addLayout(col_botao)

        layout.addLayout(dados_layout)

        # ==========================================
        # HISTÓRICO
        # ==========================================
        lbl_historico = QLabel("HISTÓRICO DE MOVIMENTAÇÕES")
        lbl_historico.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SECUNDARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; font-weight:700; "
            f"margin-top:8px;"
        )
        layout.addWidget(lbl_historico)

        self.tabela = StandardTable(
            ["Data", "Produto", "Tipo", "Quantidade", "Motivo"]
        )

        layout.addWidget(self.tabela)

        # ==========================================
        # EVENTOS
        # ==========================================
        self.bt_produto.clicked.connect(self.pesquisar_produto)
        self.bt_registrar.clicked.connect(self.registrar_ajuste)

        self.carregar()

    # ==========================================
    # PESQUISAR PRODUTO
    # ==========================================
    def pesquisar_produto(self):
        produtos = listar_produtos()

        tela = PesquisaWindow(
            titulo="Pesquisar Produto",
            colunas=["Código", "Nome", "Categoria", "Estoque"],
            campos=["codigo", "nome", "categoria", "estoque"],
            dados=produtos,
            chave_pesquisa="nome",
        )

        if tela.exec() != QDialog.Accepted:
            return

        self.produto_id = tela.selecionado["id"]

        self.produto.setText(
            f"{tela.selecionado['nome']} "
            f"(estoque atual: {tela.selecionado['estoque']})"
        )

    # ==========================================
    # CARREGAR HISTÓRICO
    # ==========================================
    def carregar(self):
        self.produtos_map = {
            produto["id"]: produto["nome"] for produto in listar_produtos()
        }

        self.movimentos = listar_movimentos()
        self.preencher_tabela(self.movimentos)

    def preencher_tabela(self, movimentos):
        self.tabela.setRowCount(len(movimentos))

        for linha, mov in enumerate(movimentos):
            data = datetime.fromisoformat(mov["data"]).strftime("%d/%m/%Y %H:%M")

            self.tabela.setItem(linha, 0, QTableWidgetItem(data))

            self.tabela.setItem(
                linha,
                1,
                QTableWidgetItem(
                    self.produtos_map.get(
                        mov["produto_id"], f"#{mov['produto_id']}"
                    )
                ),
            )

            self.tabela.setItem(
                linha,
                2,
                QTableWidgetItem(
                    "Entrada" if mov["tipo"] == "ENTRADA" else "Saída"
                ),
            )

            self.tabela.setItem(
                linha, 3, QTableWidgetItem(str(mov["quantidade"]))
            )

            self.tabela.setItem(
                linha, 4, QTableWidgetItem(mov.get("motivo") or "")
            )

    # ==========================================
    # REGISTRAR AJUSTE
    # ==========================================
    def registrar_ajuste(self):
        if self.produto_id is None:
            QMessageBox.warning(self, "Aviso", "Selecione um produto.")
            return

        try:
            quantidade = int(self.quantidade.text())
            if quantidade <= 0:
                raise ValueError

        except ValueError:
            QMessageBox.warning(
                self, "Aviso", "Informe uma quantidade válida."
            )
            return

        dados = {
            "produto_id": self.produto_id,
            "tipo": "ENTRADA" if self.tipo.currentText() == "Entrada" else "SAIDA",
            "quantidade": quantidade,
            "motivo": self.motivo.text() or None,
        }

        response = ajustar_estoque(dados)

        if response.status_code == 201:
            QMessageBox.information(
                self, "Sucesso", "Ajuste registrado com sucesso."
            )
            self._limpar()
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # LIMPAR FORMULÁRIO
    # ==========================================
    def _limpar(self):
        self.produto_id = None
        self.produto.clear()
        self.quantidade.clear()
        self.motivo.clear()
        self.tipo.setCurrentIndex(0)

    # ==========================================
    # HELPER DE ERRO
    # ==========================================
    def _exibir_erro(self, response):
        try:
            erro = response.json()["detail"]
        except Exception:
            erro = response.text

        QMessageBox.critical(self, "Erro", erro)
