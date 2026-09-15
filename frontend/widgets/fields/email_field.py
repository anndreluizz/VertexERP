"""Campo de e-mail com validação de formato ao vivo -- a borda fica
vermelha se o que foi digitado não parece um e-mail, e volta ao normal
assim que corrige. Reaproveita a mesma regra de
utils.validacao.email_valido já usada na validação de salvar em várias
telas, pra não ter duas fontes de verdade sobre o que é "e-mail
válido"."""

from design import tokens
from design.widgets import CampoTexto
from utils.validacao import email_valido


class EmailField(CampoTexto):

    def __init__(self, placeholder="email@exemplo.com", parent=None):
        super().__init__(placeholder, parent)
        self.textChanged.connect(self._validar)

    def _validar(self, texto):

        valido = email_valido(texto)
        cor_normal = tokens.BORDA if valido else tokens.ERRO
        cor_foco = tokens.PRIMARIA if valido else tokens.ERRO

        self.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {cor_normal};
                border-radius: {tokens.RADIUS_SM}px;
                padding: 0 14px;
                font-size: {tokens.TAMANHO_MD}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QLineEdit:focus {{
                border: 1.5px solid {cor_foco};
            }}
            QLineEdit:disabled {{
                background: {tokens.FUNDO};
                color: {tokens.TEXTO_TERCIARIO};
            }}
        """)

    @property
    def valido(self):
        return email_valido(self.text())
