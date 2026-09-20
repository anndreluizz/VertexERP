from datetime import datetime

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QMessageBox,
)

from services.produto_service import listar_historico_precos
from services.worker import rodar_em_thread
from widgets.tables.standard_table import StandardTable
from design import tokens


class HistoricoPrecosDialog(QDialog):
    """So' leitura -- histórico e' escrito automaticamente pelo backend
    a cada troca de preco_custo/preco_venda (ver
    ProdutoService.atualizar), nao tem edicao manual aqui."""

    def __init__(self, produto_id, nome_produto, parent=None):
        super().__init__(parent)

        self.produto_id = produto_id

        self.setWindowTitle("Histórico de Preços")
        self.resize(560, 420)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel(f"Histórico de Preços -- {nome_produto}")
        titulo.setWordWrap(True)
        titulo.setStyleSheet(
            f"background:transparent; font-size:16px; "
            f"font-weight:bold; color:{tokens.TEXTO};"
        )
        layout.addWidget(titulo)

        self.tabela = StandardTable(
            ["Data", "Usuário", "Custo (antes -> depois)", "Venda (antes -> depois)"]
        )
        layout.addWidget(self.tabela, stretch=1)

        rodape = QHBoxLayout()
        rodape.addStretch()

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
        rodape.addWidget(bt_fechar)

        layout.addLayout(rodape)

        self.carregar()

    def carregar(self):
        rodar_em_thread(
            self,
            listar_historico_precos,
            self.produto_id,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
        )

    def _ao_carregar_sucesso(self, historico):
        self.tabela.setRowCount(len(historico))

        for linha, h in enumerate(historico):
            data = datetime.fromisoformat(h["data"]).strftime(
                "%d/%m/%Y %H:%M"
            )

            self.tabela.setItem(linha, 0, QTableWidgetItem(data))
            self.tabela.setItem(
                linha, 1, QTableWidgetItem(h.get("usuario_nome") or "")
            )
            self.tabela.setItem(
                linha, 2,
                QTableWidgetItem(
                    f"R$ {h['preco_custo_anterior']:.2f} -> "
                    f"R$ {h['preco_custo_novo']:.2f}"
                ),
            )
            self.tabela.setItem(
                linha, 3,
                QTableWidgetItem(
                    f"R$ {h['preco_venda_anterior']:.2f} -> "
                    f"R$ {h['preco_venda_novo']:.2f}"
                ),
            )

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar o histórico.\n{erro}"
        )
