from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QTableWidget,
    QHeaderView,
    QAbstractItemView,
    QTableWidgetItem,
)

from design import tokens


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

        # mesmo visual da tabela do cupom no PDV -- sem isso a tabela
        # aparecia com o cabeçalho cinza padrão do Windows e grade,
        # destoando do resto das telas (usada em 8 telas)
        self.setShowGrid(False)
        self.setFrameShape(QTableWidget.NoFrame)
        self.verticalHeader().setDefaultSectionSize(40)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.horizontalHeader().setHighlightSections(False)
        self.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
                background: {tokens.CARD};
                color: {tokens.TEXTO};
                font-size: {tokens.TAMANHO_BASE}px;
                alternate-background-color: {tokens.FUNDO};
                selection-background-color: {tokens.PRIMARIA_CLARA};
                selection-color: {tokens.TEXTO};
            }}
            QHeaderView::section {{
                background: {tokens.CARD};
                color: {tokens.TEXTO_SECUNDARIO};
                font-weight: 700;
                font-size: {tokens.TAMANHO_XS}px;
                padding: 10px 12px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
            QTableWidget::item {{
                border: none;
                padding: 4px 12px;
            }}
        """)

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