from PySide6.QtWidgets import (
    QWidget,
    QGridLayout,
)

from services.api import dashboard
from widgets.card import Card


class Dashboard(QWidget):

    def __init__(self):

        super().__init__()

        layout = QGridLayout(self)

        dados = dashboard()

        self.card_vendas = Card(
            "Vendas Hoje",
            dados["vendas_hoje"],
        )

        self.card_compras = Card(
            "Compras Hoje",
            dados["compras_hoje"],
        )

        self.card_caixa = Card(
            "Saldo Caixa",
            dados["saldo_caixa"],
        )

        self.card_receber = Card(
            "Contas Receber",
            dados["contas_receber"],
        )

        self.card_pagar = Card(
            "Contas Pagar",
            dados["contas_pagar"],
        )

        self.card_clientes = Card(
            "Clientes",
            dados["clientes"],
        )

        self.card_produtos = Card(
            "Produtos",
            dados["produtos"],
        )

        self.card_fornecedores = Card(
            "Fornecedores",
            dados["fornecedores"],
        )

        layout.addWidget(self.card_vendas, 0, 0)
        layout.addWidget(self.card_compras, 0, 1)
        layout.addWidget(self.card_caixa, 0, 2)
        layout.addWidget(self.card_receber, 1, 0)
        layout.addWidget(self.card_pagar, 1, 1)
        layout.addWidget(self.card_clientes, 1, 2)
        layout.addWidget(self.card_produtos, 2, 0)
        layout.addWidget(self.card_fornecedores, 2, 1)