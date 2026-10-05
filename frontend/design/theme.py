from PySide6.QtGui import QPalette, QColor

from design import tokens
from design.fonts import carregar_fonte_inter, fonte


def aplicar_tema(app, escuro: bool = False):
    """Aplica o tema visual do Vertex ERP na aplicação inteira: fonte,
    paleta base e stylesheet global (o que toda tela herda antes de
    aplicar seu próprio stylesheet específico por cima).

    `escuro` troca a paleta de cores (ver design.tokens.aplicar) antes
    de montar a QPalette/QSS abaixo, e precisa ser decidido ANTES de
    qualquer tela ser construída -- trocar em runtime com telas já
    abertas não re-tinge o que já foi desenhado (ver Header.
    _alternar_tema, que reinicia o app pra aplicar de verdade)."""

    tokens.aplicar(escuro)

    familia_fonte = carregar_fonte_inter()

    app.setStyle("Fusion")
    app.setFont(fonte(tokens.TAMANHO_BASE))

    paleta = QPalette()
    paleta.setColor(QPalette.Window, QColor(tokens.FUNDO))
    paleta.setColor(QPalette.WindowText, QColor(tokens.TEXTO))
    paleta.setColor(QPalette.Base, QColor(tokens.CARD))
    paleta.setColor(QPalette.AlternateBase, QColor(tokens.FUNDO))
    paleta.setColor(QPalette.ToolTipBase, QColor(tokens.TEXTO))
    paleta.setColor(QPalette.ToolTipText, QColor(tokens.TEXTO_CLARO))
    paleta.setColor(QPalette.Text, QColor(tokens.TEXTO))
    paleta.setColor(QPalette.Button, QColor(tokens.CARD))
    paleta.setColor(QPalette.ButtonText, QColor(tokens.TEXTO))
    paleta.setColor(QPalette.Highlight, QColor(tokens.PRIMARIA))
    paleta.setColor(QPalette.HighlightedText, QColor(tokens.TEXTO_CLARO))
    paleta.setColor(QPalette.PlaceholderText, QColor(tokens.TEXTO_TERCIARIO))
    paleta.setColor(
        QPalette.Disabled, QPalette.Text, QColor(tokens.TEXTO_TERCIARIO)
    )
    paleta.setColor(
        QPalette.Disabled, QPalette.WindowText, QColor(tokens.TEXTO_TERCIARIO)
    )

    app.setPalette(paleta)

    app.setStyleSheet(f"""
        QWidget {{
            font-family: "{familia_fonte}";
        }}

        QToolTip {{
            background: {tokens.TEXTO};
            color: {tokens.TEXTO_CLARO};
            border: none;
            border-radius: {tokens.RADIUS_SM}px;
            padding: 6px 10px;
        }}

        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {tokens.BORDA_FORTE};
            border-radius: 5px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {tokens.TEXTO_TERCIARIO};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            background: transparent;
            height: 10px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal {{
            background: {tokens.BORDA_FORTE};
            border-radius: 5px;
            min-width: 24px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        QMessageBox {{
            background: {tokens.CARD};
        }}
    """)

    return familia_fonte
