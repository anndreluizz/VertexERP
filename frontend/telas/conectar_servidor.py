from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)

import requests

from design import tokens
from design.icons import icone_pixmap
from design.widgets import BotaoPrimario, BotaoSecundario, CampoTexto
from services import api
from services.preferencias_service import salvar_servidor, carregar_servidor


class ConectarServidorDialog(QDialog):
    """Configura o endereço do PC-servidor pra uma instalação Terminal
    (só o frontend, sem backend/banco locais). Permite salvar mesmo se
    o teste de conexão falhar — o servidor pode simplesmente ainda não
    estar ligado no momento em que o terminal está sendo configurado."""

    def __init__(self, parent=None):

        super().__init__(parent)

        self.confirmado = False

        self.setWindowTitle("Conectar ao Servidor")
        self.setFixedSize(420, 430)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(8)

        icone = QLabel()
        icone.setFixedSize(56, 56)
        icone.setAlignment(Qt.AlignCenter)
        icone.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; border-radius:28px;
        """)
        icone.setPixmap(icone_pixmap("store", cor=tokens.PRIMARIA, tamanho=24))

        layout.addWidget(icone, alignment=Qt.AlignHCenter)
        layout.addSpacing(6)

        titulo = QLabel("Conectar ao Servidor")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            "Este computador é um caixa (terminal) — informe o endereço "
            "do PC que funciona como servidor da loja."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO};
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(12)

        lbl_campo = QLabel("ENDEREÇO DO SERVIDOR")
        lbl_campo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.endereco = CampoTexto("Ex.: 192.168.0.10")
        self.endereco.setText(carregar_servidor() or "")
        self.endereco.setMinimumHeight(44)

        layout.addWidget(lbl_campo)
        layout.addWidget(self.endereco)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setMinimumHeight(50)
        self.lbl_status.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        linha_botoes = QHBoxLayout()
        linha_botoes.setSpacing(10)

        bt_testar = BotaoSecundario("Testar Conexão")
        bt_testar.setMinimumHeight(44)
        bt_testar.clicked.connect(self.testar)

        bt_salvar = BotaoPrimario("Salvar")
        bt_salvar.setMinimumHeight(44)
        bt_salvar.clicked.connect(self.salvar)

        linha_botoes.addWidget(bt_testar)
        linha_botoes.addWidget(bt_salvar)

        layout.addLayout(linha_botoes)

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.setMinimumHeight(40)
        bt_fechar.clicked.connect(self.reject)

        layout.addWidget(bt_fechar)

    def testar(self):

        endereco = self.endereco.text().strip()

        if not endereco:
            self._status("Informe um endereço.", tokens.ALERTA)
            return

        api.definir_url(endereco)

        try:
            resposta = requests.get(f"{api.URL}/", timeout=3)
            ok = resposta.status_code == 200
        except Exception:
            ok = False

        if ok:
            self._status(f"Conectado com sucesso em {api.URL}!", tokens.SECUNDARIA)
        else:
            self._status(
                "Não foi possível conectar agora — confira se o servidor "
                "está ligado e na mesma rede. Você ainda pode salvar e "
                "tentar de novo depois.",
                tokens.ALERTA,
            )

    def salvar(self):

        endereco = self.endereco.text().strip()

        if not endereco:
            self._status("Informe um endereço.", tokens.ALERTA)
            return

        api.definir_url(endereco)
        salvar_servidor(endereco)

        self.confirmado = True
        self.accept()

    def _status(self, texto, cor):
        self.lbl_status.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px; color:{cor};
        """)
        self.lbl_status.setText(texto)
