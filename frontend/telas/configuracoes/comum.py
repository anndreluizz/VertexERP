from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
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

        cor_icone = tokens.TEXTO_SECUNDARIO if habilitado else tokens.TEXTO_TERCIARIO
        self.setIcon(icone(icone_nome, cor=cor_icone, tamanho=17))
        self.setIconSize(QSize(17, 17))

        if habilitado:
            self.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; text-align:left; padding-left:12px;
                    border:none; border-radius:{tokens.RADIUS_SM}px;
                    color:{tokens.TEXTO_SECUNDARIO}; font-size:{tokens.TAMANHO_MD}px;
                }}
                QPushButton:hover {{ background:{tokens.FUNDO}; color:{tokens.TEXTO}; }}
                QPushButton:checked {{
                    background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA};
                    font-weight:700;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; text-align:left; padding-left:12px;
                    border:none; border-radius:{tokens.RADIUS_SM}px;
                    color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_SM}px;
                }}
            """)
