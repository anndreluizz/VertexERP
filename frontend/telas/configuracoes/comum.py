from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QPushButton,
)


from design import tokens
from design.icons import icone


_SECOES = [
    ("store", "Geral", "Nome, documento, contato e logo que aparecem nos comprovantes."),
    ("credit-card", "Pagamentos e PIX", "Chave PIX usada no QR Code de cobrança do PDV."),
    ("shopping-cart", "Atalhos do PDV", "Teclas de atalho do caixa. Valem só pra quem está logado."),
    ("message-circle", "WhatsApp", "Mensagens automáticas pros clientes pelo WhatsApp da loja."),
    ("mail", "E-mail", "Servidor de e-mail pra mandar comprovantes por e-mail."),
    ("printer", "Impressora e cupom", "Impressora térmica dos comprovantes e extratos."),
    ("settings", "Hardware e scanner", "Leitor de código de barras e outros aparelhos."),
    ("truck", "Lojas e filiais", "Lojas cadastradas e a loja deste computador."),
    ("download", "Backup", "Cópias de segurança do banco de dados."),
]


# seções salvas pelo botão "Salvar alterações" do rodapé (as outras têm
# botão próprio dentro da seção)
_SECOES_DO_RODAPE = {0, 1, 3, 4}


class ItemMenuConfig(QPushButton):

    def __init__(self, icone_nome, texto, habilitado=True):

        super().__init__(texto if habilitado else f"{texto}  ·  em breve")

        self.setCheckable(True)
        self.setEnabled(habilitado)
        self.setMinimumHeight(42)
        self.setCursor(
            Qt.PointingHandCursor if habilitado else Qt.ArrowCursor
        )

        cor_icone = tokens.TEXTO if habilitado else tokens.TEXTO_TERCIARIO
        self.setIcon(icone(icone_nome, cor=cor_icone, tamanho=17))
        self.setIconSize(QSize(17, 17))
        # Vertex 2.0: escolhido = azul cheio, icone branco
        self.toggled.connect(lambda marcado: self.setIcon(
            icone(icone_nome, cor="#FFFFFF" if marcado else cor_icone, tamanho=17)))

        if habilitado:
            self.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; text-align:left; padding-left:12px;
                    border:none; border-radius:{tokens.RADIUS_SM}px;
                    color:{tokens.TEXTO}; font-size:{tokens.TAMANHO_MD}px; font-weight:600;
                }}
                QPushButton:hover {{ background:{tokens.CARD}; }}
                QPushButton:checked {{ background:{tokens.PRIMARIA}; color:#FFFFFF; }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; text-align:left; padding-left:12px;
                    border:none; border-radius:{tokens.RADIUS_SM}px;
                    color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_SM}px;
                }}
            """)


class Interruptor(QCheckBox):
    """Liga/desliga (prototipo Config2). Continua sendo um QCheckBox
    (isChecked/toggled), so' desenha o trilho com a bolinha."""

    def __init__(self, rotulo=""):
        super().__init__()
        self.setFixedSize(52, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(rotulo)

    def hitButton(self, _pos):
        return True

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(tokens.SECUNDARIA if self.isChecked() else tokens.BORDA_FORTE))
        p.drawRoundedRect(QRectF(0, 0, 52, 30), 15, 15)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(25 if self.isChecked() else 3, 3, 24, 24))
        p.end()


_SIGLAS = {"PIX", "CNPJ", "CPF", "ID", "SMTP", "IP", "USB", "PDV", "Z-API)", "(Z-API)", "QR"}


def frase(texto):
    """'NOME DA LOJA' -> 'Nome da loja' (mantem siglas: 'CHAVE PIX' ->
    'Chave PIX')."""
    if not texto.isupper():
        return texto
    palavras = texto.replace("WHATSAPP", "WhatsApp").split()
    saida = []
    for i, pal in enumerate(palavras):
        if pal.strip("()/:") in _SIGLAS or pal in _SIGLAS or pal == "WhatsApp":
            saida.append(pal)
        else:
            pal = pal.lower()
            saida.append(pal[:1].upper() + pal[1:] if i == 0 else pal)
    return " ".join(saida)
