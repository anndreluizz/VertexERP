from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
)

from services.api import trocar_senha
from services.worker import rodar_em_thread

from design import tokens
from design.responsive import tamanho_fixo_seguro
from design.widgets import BotaoSecundario, BotaoSucesso


class TrocarSenhaDialog(QDialog):
    """Autoatendimento -- o usuário troca a própria senha, confirmando
    a atual antes (ver /auth/senha). Pra redefinir a senha de outra
    pessoa (funcionário esqueceu a senha), ver RedefinirSenhaDialog em
    gerenciar_usuarios.py, que é o admin fazendo isso, não a própria
    pessoa."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Trocar Senha")
        tamanho_fixo_seguro(self, 400, 380)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        titulo = QLabel("Trocar Senha")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel("Confirme a senha atual pra definir uma nova.")
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(10)

        self.senha_atual = self._campo(layout, "SENHA ATUAL")
        self.senha_nova = self._campo(layout, "NOVA SENHA")
        self.confirmar = self._campo(layout, "CONFIRMAR NOVA SENHA")

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.setMinimumHeight(44)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        self.bt_salvar = BotaoSucesso("Salvar")
        self.bt_salvar.setMinimumHeight(44)
        self.bt_salvar.setAutoDefault(False)
        self.bt_salvar.clicked.connect(self.salvar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(self.bt_salvar)

        layout.addLayout(botoes)

        self.senha_atual.setFocus()

    def _campo(self, layout, rotulo):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        campo = QLineEdit()
        campo.setPlaceholderText("••••••")
        campo.setEchoMode(QLineEdit.Password)
        campo.setMinimumHeight(40)
        campo.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QLineEdit:focus {{ border: 1.5px solid {tokens.PRIMARIA}; }}
        """)

        layout.addWidget(lbl)
        layout.addWidget(campo)

        return campo

    def salvar(self):

        senha_atual = self.senha_atual.text()
        senha_nova = self.senha_nova.text()
        confirmar = self.confirmar.text()

        if not senha_atual or not senha_nova:
            QMessageBox.warning(
                self, "Atenção", "Preencha todos os campos."
            )
            return

        if senha_nova != confirmar:
            QMessageBox.warning(
                self, "Atenção", "A nova senha e a confirmação não coincidem."
            )
            return

        self.bt_salvar.setEnabled(False)

        rodar_em_thread(
            self,
            trocar_senha,
            senha_atual,
            senha_nova,
            ao_sucesso=self._ao_salvar_sucesso,
            ao_erro=self._ao_salvar_erro,
            ao_finalizar=self._ao_salvar_finalizado,
        )

    def _ao_salvar_sucesso(self, response):

        if response.status_code == 200:
            QMessageBox.information(
                self, "Sucesso", "Senha alterada com sucesso."
            )
            self.accept()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_salvar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_salvar_finalizado(self):
        self.bt_salvar.setEnabled(True)
