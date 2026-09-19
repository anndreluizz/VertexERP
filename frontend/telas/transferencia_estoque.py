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
from services.loja_service import listar_lojas
from services.estoque_service import listar_transferencias, transferir_estoque
from services.worker import rodar_em_thread, em_paralelo
from widgets.dialogs.pesquisa_window import PesquisaWindow
from widgets.tables.standard_table import StandardTable
from design import tokens


def _buscar_dados_transferencia():
    """Roda na worker thread -- as 3 chamadas que carregar() precisa,
    independentes entre si, disparadas em paralelo (mesmo padrao de
    ajuste_estoque.py)."""
    produtos, lojas, transferencias = em_paralelo(
        (listar_produtos,), (listar_lojas,), (listar_transferencias,)
    )
    produtos_map = {p["id"]: p["nome"] for p in produtos}
    lojas_map = {l["id"]: l["nome"] for l in lojas}
    return produtos_map, lojas_map, transferencias


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


class TransferenciaEstoque(QWidget):

    def __init__(self):
        super().__init__()

        self.produto_id = None
        self.lojas = []
        self._carregando = False

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        titulo = QLabel("Transferência de Estoque")
        titulo.setStyleSheet(
            f"background:transparent; font-size:{tokens.TAMANHO_XL}px; "
            f"font-weight:800; color:{tokens.TEXTO};"
        )
        layout.addWidget(titulo)

        subtitulo = QLabel(
            "Mova produto de uma loja pra outra -- dá saída na origem e "
            "entrada no destino ao mesmo tempo, tudo registrado no "
            "histórico de movimentações."
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
        # LOJA DESTINO / QUANTIDADE / MOTIVO
        # ==========================================
        dados_layout = QHBoxLayout()
        dados_layout.setSpacing(12)

        col_destino = QVBoxLayout()
        col_destino.setSpacing(4)
        lbl_destino = QLabel("LOJA DESTINO")
        lbl_destino.setStyleSheet(_estilo_rotulo())
        col_destino.addWidget(lbl_destino)

        self.loja_destino = QComboBox()
        self.loja_destino.setMinimumHeight(38)
        self.loja_destino.setStyleSheet(_estilo_campo())
        col_destino.addWidget(self.loja_destino)
        dados_layout.addLayout(col_destino)

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
        lbl_motivo = QLabel("MOTIVO (opcional)")
        lbl_motivo.setStyleSheet(_estilo_rotulo())
        col_motivo.addWidget(lbl_motivo)

        self.motivo = QLineEdit()
        self.motivo.setPlaceholderText("Ex.: reposição, redistribuição...")
        self.motivo.setMinimumHeight(38)
        self.motivo.setStyleSheet(_estilo_campo())
        col_motivo.addWidget(self.motivo)
        dados_layout.addLayout(col_motivo, stretch=1)

        col_botao = QVBoxLayout()
        col_botao.setSpacing(4)
        col_botao.addWidget(QLabel(""))  # alinha o botao com os campos

        self.bt_transferir = QPushButton("Transferir")
        self.bt_transferir.setMinimumHeight(38)
        self.bt_transferir.setCursor(Qt.PointingHandCursor)
        self.bt_transferir.setStyleSheet(f"""
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
        col_botao.addWidget(self.bt_transferir)
        dados_layout.addLayout(col_botao)

        layout.addLayout(dados_layout)

        # ==========================================
        # HISTÓRICO
        # ==========================================
        lbl_historico = QLabel("HISTÓRICO DE TRANSFERÊNCIAS")
        lbl_historico.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SECUNDARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; font-weight:700; "
            f"margin-top:8px;"
        )
        layout.addWidget(lbl_historico)

        self.tabela = StandardTable(
            ["Data", "Produto", "Origem", "Destino", "Quantidade", "Motivo"]
        )

        layout.addWidget(self.tabela)

        # ==========================================
        # EVENTOS
        # ==========================================
        self.bt_produto.clicked.connect(self.pesquisar_produto)
        self.bt_transferir.clicked.connect(self.registrar_transferencia)

        self.carregar()

    # ==========================================
    # PESQUISAR PRODUTO
    # ==========================================
    def pesquisar_produto(self):
        self.bt_produto.setEnabled(False)
        rodar_em_thread(
            self,
            listar_produtos,
            ao_sucesso=self._ao_pesquisar_produto_sucesso,
            ao_erro=self._ao_pesquisar_produto_erro,
            ao_finalizar=self._ao_pesquisar_produto_finalizado,
        )

    def _ao_pesquisar_produto_sucesso(self, produtos):

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

    def _ao_pesquisar_produto_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível buscar produtos.\n{erro}")

    def _ao_pesquisar_produto_finalizado(self):
        self.bt_produto.setEnabled(True)

    # ==========================================
    # CARREGAR (lojas + historico)
    # ==========================================
    def carregar(self):
        if self._carregando:
            return
        self._carregando = True
        self.bt_transferir.setEnabled(False)

        rodar_em_thread(
            self,
            _buscar_dados_transferencia,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _ao_carregar_sucesso(self, resultado):
        try:
            self.produtos_map, self.lojas_map, transferencias = resultado

            self.loja_destino.blockSignals(True)
            self.loja_destino.clear()
            for loja_id, nome in self.lojas_map.items():
                self.loja_destino.addItem(nome, loja_id)
            self.loja_destino.blockSignals(False)

            self.preencher_tabela(transferencias)
        except Exception as erro:
            self._ao_carregar_erro(erro)

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar os dados.\n{erro}")

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self.bt_transferir.setEnabled(True)

    def preencher_tabela(self, transferencias):
        self.tabela.setRowCount(len(transferencias))

        for linha, t in enumerate(transferencias):
            data = datetime.fromisoformat(t["data"]).strftime("%d/%m/%Y %H:%M")

            self.tabela.setItem(linha, 0, QTableWidgetItem(data))
            self.tabela.setItem(
                linha, 1,
                QTableWidgetItem(
                    self.produtos_map.get(t["produto_id"], f"#{t['produto_id']}")
                ),
            )
            self.tabela.setItem(
                linha, 2,
                QTableWidgetItem(
                    self.lojas_map.get(t["loja_origem_id"], f"#{t['loja_origem_id']}")
                ),
            )
            self.tabela.setItem(
                linha, 3,
                QTableWidgetItem(
                    self.lojas_map.get(t["loja_destino_id"], f"#{t['loja_destino_id']}")
                ),
            )
            self.tabela.setItem(
                linha, 4, QTableWidgetItem(str(t["quantidade"]))
            )
            self.tabela.setItem(
                linha, 5, QTableWidgetItem(t.get("motivo") or "")
            )

    # ==========================================
    # REGISTRAR TRANSFERENCIA
    # ==========================================
    def registrar_transferencia(self):
        if self.produto_id is None:
            QMessageBox.warning(self, "Aviso", "Selecione um produto.")
            return

        if self.loja_destino.currentData() is None:
            QMessageBox.warning(self, "Aviso", "Selecione a loja destino.")
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
            "loja_destino_id": self.loja_destino.currentData(),
            "quantidade": quantidade,
            "motivo": self.motivo.text() or None,
        }

        self.bt_transferir.setEnabled(False)

        rodar_em_thread(
            self,
            transferir_estoque,
            dados,
            ao_sucesso=self._ao_registrar_sucesso,
            ao_erro=self._ao_registrar_erro,
            ao_finalizar=self._ao_registrar_finalizado,
        )

    def _ao_registrar_sucesso(self, response):
        if response.status_code == 201:
            QMessageBox.information(
                self, "Sucesso", "Transferência registrada com sucesso."
            )
            self._limpar()
            self.carregar()
        else:
            self._exibir_erro(response)

    def _ao_registrar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_registrar_finalizado(self):
        if not self._carregando:
            self.bt_transferir.setEnabled(True)

    # ==========================================
    # LIMPAR FORMULÁRIO
    # ==========================================
    def _limpar(self):
        self.produto_id = None
        self.produto.clear()
        self.quantidade.clear()
        self.motivo.clear()

    # ==========================================
    # HELPER DE ERRO
    # ==========================================
    def _exibir_erro(self, response):
        try:
            erro = response.json()["detail"]
        except Exception:
            erro = response.text

        QMessageBox.critical(self, "Erro", erro)
