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
from services.worker import rodar_em_thread
from design import tokens
from design.responsive import tamanho_fixo_seguro


class CadastrarLojaDialog(QDialog):

    loja_salva = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Cadastrar Nova Loja")
        tamanho_fixo_seguro(self, 420, 320)
        self.setStyleSheet(f"background:{tokens.CARD}; border-radius:16px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 28)
        layout.setSpacing(6)

        icone = QLabel("🏠")
        icone.setFixedSize(56, 56)
        icone.setAlignment(Qt.AlignCenter)
        icone.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA};
            color:{tokens.PRIMARIA};
            border-radius:14px;
            font-size:24px;
        """)

        layout.addWidget(icone)
        layout.addSpacing(16)

        titulo = QLabel("Cadastrar Nova Loja")
        titulo.setStyleSheet(
            f"background:transparent; font-size:19px; "
            f"font-weight:bold; color:{tokens.TEXTO};"
        )

        subtitulo = QLabel(
            "Defina o nome da sua loja pra começar a vender."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(
            f"background:transparent; font-size:12px; color:{tokens.TEXTO_TERCIARIO};"
        )

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(20)

        lbl_campo = QLabel("NOME DA LOJA")
        lbl_campo.setStyleSheet(
            f"background:transparent; font-size:10px; "
            f"font-weight:bold; color:{tokens.TEXTO_TERCIARIO};"
        )

        self.nome_loja = QLineEdit()
        self.nome_loja.setPlaceholderText("Ex: Loja do João")
        self.nome_loja.setMinimumHeight(44)
        self.nome_loja.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid {tokens.PRIMARIA};
                border-radius: 10px;
                padding: 0 14px;
                font-size: 14px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
        """)

        layout.addWidget(lbl_campo)
        layout.addWidget(self.nome_loja)

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = QPushButton("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.FUNDO};
                color:{tokens.TEXTO};
                border-radius:10px;
            }}
            QPushButton:hover {{
                background:{tokens.BORDA};
            }}
        """)
        bt_cancelar.clicked.connect(self.pular)

        self.bt_salvar = QPushButton("SALVAR LOJA  ✓")
        self.bt_salvar.setMinimumHeight(46)
        self.bt_salvar.setAutoDefault(False)
        self.bt_salvar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.PRIMARIA};
                color:{tokens.TEXTO_CLARO};
                font-weight:bold;
                border-radius:10px;
            }}
            QPushButton:hover {{
                background:{tokens.PRIMARIA_HOVER};
            }}
        """)
        self.bt_salvar.clicked.connect(self.salvar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(self.bt_salvar)

        layout.addLayout(botoes)

        self.nome_loja.setFocus()

    def salvar(self):

        nome = self.nome_loja.text().strip()

        if not nome:
            QMessageBox.warning(
                self, "Atenção", "Informe o nome da loja."
            )
            return

        self.bt_salvar.setEnabled(False)

        rodar_em_thread(
            self,
            atualizar_configuracoes,
            {"nome_loja": nome},
            ao_sucesso=self._ao_salvar_sucesso,
            ao_erro=self._ao_salvar_erro,
            ao_finalizar=self._ao_salvar_finalizado,
        )

    def _ao_salvar_sucesso(self, response):

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

    def _ao_salvar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_salvar_finalizado(self):
        self.bt_salvar.setEnabled(True)

    def pular(self):
        self.loja_salva.emit()
        self.reject()
