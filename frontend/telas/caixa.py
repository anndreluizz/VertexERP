from telas.suprimento import SuprimentoWindow
from telas.sangria import SangriaWindow

from PySide6.QtCore import Qt
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
    QInputDialog,
    QFrame,          # <-- adicionar
    QDialog,
)

from services.caixa_service import (
    caixa_aberto,
    abrir_caixa,
    fechar_caixa,
    listar_movimentacoes,
)

from services.movimento_caixa_service import (
    criar_sangria,
    criar_suprimento,
)

from services.api import usuario_e_admin


class Caixa(QWidget):

    def __init__(self):
        super().__init__()

        self.setStyleSheet("""

        QWidget{
            font-size:13px;
        }

        QLabel#titulo{
            font-size:26px;
            font-weight:bold;
            color:#1565C0;
        }

        QFrame{
            background:white;
            border:1px solid #D9D9D9;
            border-radius:8px;
        }

        QFrame QLabel{
            color:#212121;
        }

        QPushButton{
            background:#1565C0;
            color:white;
            border:none;
            border-radius:6px;
            padding:10px;
            font-weight:bold;
        }

        QPushButton:hover{
            background:#0D47A1;
        }

        QTableWidget{
            background:white;
            color:#212121;
            gridline-color:#DDDDDD;
        }

        QTableWidget::item{
            color:#212121;
        }

        QHeaderView::section{
            background:#F0F0F0;
            color:#212121;
            padding:6px;
            border:1px solid #D9D9D9;
            font-weight:bold;
        }

        """)

        layout = QVBoxLayout(self)

        # ======================================
        # TÍTULO
        # ======================================

        titulo = QLabel("CAIXA")

        titulo.setObjectName("titulo")

        titulo.setAlignment(Qt.AlignCenter)

        layout.addWidget(titulo)

        # ======================================
        # CARDS
        # ======================================

        cards = QHBoxLayout()

        self.card_status = QLabel("🔴 FECHADO")
        self.card_operador = QLabel("Operador\n---")
        self.card_saldo = QLabel("Saldo Inicial\nR$ 0,00")
        self.card_movimentos = QLabel("Movimentos\n0")

        for card in (
            self.card_status,
            self.card_operador,
            self.card_saldo,
            self.card_movimentos,
        ):

            frame = QFrame()

            frame_layout = QVBoxLayout(frame)

            card.setAlignment(Qt.AlignCenter)

            card.setStyleSheet("""
                font-size:16px;
                font-weight:bold;
                padding:12px;
            """)

            frame_layout.addWidget(card)

            cards.addWidget(frame)

        layout.addLayout(cards)

        # ======================================
        # BOTÕES
        # ======================================

        botoes = QHBoxLayout()

        self.bt_abrir = QPushButton("Abrir Caixa")
        self.bt_fechar = QPushButton("Fechar Caixa")
        self.bt_sangria = QPushButton("Sangria")
        self.bt_suprimento = QPushButton("Suprimento")
        self.bt_atualizar = QPushButton("Atualizar")

        # Fechar caixa é uma ação de administrador — operadores não veem o botão.
        if not usuario_e_admin():
            self.bt_fechar.setVisible(False)

        botoes.addWidget(self.bt_abrir)
        botoes.addWidget(self.bt_fechar)
        botoes.addWidget(self.bt_sangria)
        botoes.addWidget(self.bt_suprimento)

        botoes.addStretch()

        botoes.addWidget(self.bt_atualizar)

        layout.addLayout(botoes)

        # ======================================
        # TABELA
        # ======================================

        self.tabela = QTableWidget()

        self.tabela.setColumnCount(4)

        self.tabela.setHorizontalHeaderLabels([
            "Data/Hora",
            "Tipo",
            "Valor",
            "Descrição",
        ])

        self.tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.tabela.verticalHeader().setVisible(False)

        self.tabela.setAlternatingRowColors(True)

        layout.addWidget(self.tabela)

        # ======================================
        # EVENTOS
        # ======================================

        self.bt_atualizar.clicked.connect(
            self.carregar
        )

        self.bt_abrir.clicked.connect(
            self.abrir_caixa
        )

        self.bt_fechar.clicked.connect(
            self.fechar_caixa
        )

        self.bt_sangria.clicked.connect(
            self.sangria
        )

        self.bt_suprimento.clicked.connect(
            self.suprimento
        )

        self.carregar()

    # ======================================
    # CARREGAR DADOS
    # ======================================

    def carregar(self):

        caixa = caixa_aberto()

        movimentos = listar_movimentacoes()

        self.tabela.setRowCount(0)

        if caixa is None:

            self.card_status.setText("🔴 FECHADO")
            self.card_operador.setText("Operador\n---")
            self.card_saldo.setText("Saldo Inicial\nR$ 0,00")
            self.card_movimentos.setText(
                f"Movimentos\n{len(movimentos)}"
            )

        else:

            self.card_status.setText(
                f"🟢 {caixa['status']}"
            )

            self.card_operador.setText(
                "Operador\nAdministrador"
            )

            self.card_saldo.setText(
                f"Saldo Inicial\nR$ {float(caixa['saldo_inicial']):.2f}"
            )

            self.card_movimentos.setText(
                f"Movimentos\n{len(movimentos)}"
            )

        self.tabela.setRowCount(len(movimentos))

        for linha, mov in enumerate(movimentos):

            data = str(mov["data"])

            if "T" in data:
                data = data.replace("T", " ")

            self.tabela.setItem(
                linha,
                0,
                QTableWidgetItem(data[:19])
            )

            self.tabela.setItem(
                linha,
                1,
                QTableWidgetItem(mov["tipo"])
            )

            self.tabela.setItem(
                linha,
                2,
                QTableWidgetItem(
                    f"R$ {float(mov['valor']):.2f}"
                )
            )

            self.tabela.setItem(
                linha,
                3,
                QTableWidgetItem(
                    mov.get("descricao", "")
                )
            )

    # ======================================
    # ABRIR CAIXA
    # ======================================

    def abrir_caixa(self):

        valor, ok = QInputDialog.getDouble(
            self,
            "Abrir Caixa",
            "Saldo Inicial:",
            0,
            0,
            999999,
            2,
        )

        if not ok:
            return

        response = abrir_caixa(valor)

        if response.status_code == 200:

            QMessageBox.information(
                self,
                "Sucesso",
                "Caixa aberto com sucesso!"
            )

            self.carregar()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.warning(
                self,
                "Erro",
                erro
            )

    # ======================================
    # FECHAR CAIXA
    # ======================================

    def fechar_caixa(self):

        resposta = QMessageBox.question(
            self,
            "Fechar Caixa",
            "Deseja realmente fechar o caixa?"
        )

        if resposta != QMessageBox.Yes:
            return

        response = fechar_caixa()

        if response.status_code == 200:

            QMessageBox.information(
                self,
                "Sucesso",
                "Caixa fechado com sucesso!"
            )

            self.carregar()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.warning(
                self,
                "Erro",
                erro
            )

    # ======================================
    # SANGRIA
    # ======================================

    def sangria(self):

        janela = SangriaWindow()

        if janela.exec() != QDialog.Accepted:
            return

        dados = janela.dados

        response = criar_sangria(
            dados["valor"],
            dados["descricao"],
        )

        if response.status_code == 200:

            QMessageBox.information(
                self,
                "Sucesso",
                "Sangria registrada com sucesso."
            )

            self.carregar()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(
                self,
                "Erro",
                erro,
            )

    # ======================================
    # SUPRIMENTO
    # ======================================

    def suprimento(self):

        janela = SuprimentoWindow()

        if janela.exec() != QDialog.Accepted:
            return

        dados = janela.dados

        response = criar_suprimento(
            dados["valor"],
            dados["descricao"],
        )

        if response.status_code == 200:

            QMessageBox.information(
                self,
                "Sucesso",
                "Suprimento registrado com sucesso."
            )

            self.carregar()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(
                self,
                "Erro",
                erro,
            )