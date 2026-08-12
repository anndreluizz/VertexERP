from PySide6.QtWidgets import (
    QTableWidget,
    QHeaderView,
    QAbstractItemView,
    QTableWidgetItem,
)


class StandardTable(QTableWidget):

    def __init__(self, colunas):
        super().__init__()

        self.setColumnCount(len(colunas))
        self.setHorizontalHeaderLabels(colunas)

        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.verticalHeader().setVisible(False)

        self.setAlternatingRowColors(True)

        self.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.setSelectionMode(
            QAbstractItemView.SingleSelection
        )

        self.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

    def preencher(
        self,
        registros,
        campos,
    ):

        self.setRowCount(len(registros))

        for linha, registro in enumerate(registros):

            for coluna, campo in enumerate(campos):

                valor = registro.get(campo)

                if campo == "ativo":
                    valor = "Ativo" if valor else "Inativo"

                if valor is None:
                    valor = ""

                self.setItem(
                    linha,
                    coluna,
                    QTableWidgetItem(str(valor))
                )

    def limpar(self):

        self.setRowCount(0)