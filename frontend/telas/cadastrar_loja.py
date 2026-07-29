from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)

from services.api import atualizar_configuracoes


class CadastrarLojaDialog(QDialog):

    loja_salva = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Cadastrar Nova Loja")
        self.setFixedSize(420, 320)
        self.setStyleSheet("background:white; border-radius:16px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 28)
        layout.setSpacing(6)

        icone = QLabel("🏠")
        icone.setFixedSize(56, 56)
        icone.setAlignment(Qt.AlignCenter)
        icone.setStyleSheet("""
            background:#E3F2FD;
            color:#1565C0;
            border-radius:14px;
            font-size:24px;
        """)

        layout.addWidget(icone)
        layout.addSpacing(16)

        titulo = QLabel("Cadastrar Nova Loja")
        titulo.setStyleSheet(
            "background:transparent; font-size:19px; "
            "font-weight:bold; color:#202225;"
        )

        subtitulo = QLabel(
            "Defina o nome da sua loja pra começar a vender."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(
            "background:transparent; font-size:12px; color:gray;"
        )

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(20)

        lbl_campo = QLabel("NOME DA LOJA")
        lbl_campo.setStyleSheet(
            "background:transparent; font-size:10px; "
            "font-weight:bold; color:#757575;"
        )

        self.nome_loja = QLineEdit()
        self.nome_loja.setPlaceholderText("Ex: Loja do João")
        self.nome_loja.setMinimumHeight(44)
        self.nome_loja.setStyleSheet("""
            QLineEdit {
                border: 2px solid #1565C0;
                border-radius: 10px;
                padding: 0 14px;
                font-size: 14px;
                color: #202225;
            }
        """)

        layout.addWidget(lbl_campo)
        layout.addWidget(self.nome_loja)

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = QPushButton("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.setStyleSheet("""
            QPushButton {
                background:#f4f5f7;
                color:#202225;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        bt_cancelar.clicked.connect(self.pular)

        bt_salvar = QPushButton("SALVAR LOJA  ✓")
        bt_salvar.setMinimumHeight(46)
        bt_salvar.setAutoDefault(False)
        bt_salvar.setStyleSheet("""
            QPushButton {
                background:#1565C0;
                color:white;
                font-weight:bold;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#0D47A1;
            }
        """)
        bt_salvar.clicked.connect(self.salvar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(bt_salvar)

        layout.addLayout(botoes)

        self.nome_loja.setFocus()

    def salvar(self):

        nome = self.nome_loja.text().strip()

        if not nome:
            QMessageBox.warning(
                self, "Atenção", "Informe o nome da loja."
            )
            return

        response = atualizar_configuracoes({"nome_loja": nome})

        if response.status_code != 200:

            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))
            return

        self.loja_salva.emit()
        self.accept()

    def pular(self):
        self.loja_salva.emit()
        self.reject()
