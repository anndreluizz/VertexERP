import os
import tempfile

from PySide6.QtGui import QPalette, QColor

from design import tokens
from design.fonts import carregar_fonte_inter, fonte
from design import teclado


def _chevrons():
    """(caminho do chevron pra baixo, pra cima) na cor do tema. O QSS só
    aceita `image: url(arquivo)` e o ícone do Lucide usa currentColor,
    então gera um SVG com a cor de verdade numa pasta temporária."""

    pasta = os.path.join(tempfile.gettempdir(), "vertex_erp_icones")
    os.makedirs(pasta, exist_ok=True)
    cor = tokens.TEXTO_TERCIARIO
    caminhos = []
    for nome, caminho in (("baixo", "m6 9 6 6 6-6"), ("cima", "m18 15-6-6-6 6")):
        arquivo = os.path.join(pasta, f"chevron-{nome}-{cor.lstrip('#')}.svg")
        if not os.path.exists(arquivo):
            with open(arquivo, "w", encoding="utf-8") as f:
                f.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
                    'viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="2.4" '
                    'stroke-linecap="round" stroke-linejoin="round"><path d="%s"/></svg>'
                    % (cor, caminho)
                )
        caminhos.append(arquivo.replace("\\", "/"))
    return caminhos


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

    seta_baixo, seta_cima = _chevrons()

    app.setStyleSheet(f"""
        QWidget {{
            font-family: "{familia_fonte}";
            font-weight: 500;  /* 06/11: Figtree 400 ficava fina demais no Windows */
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

        /* botao da setinha de combos/datas e botoes dos campos numericos:
           sem isso o Qt desenha o desenho nativo (uma barra escura no canto
           direito) por cima da borda que cada formulario define */
        QComboBox::drop-down, QDateEdit::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 34px;
            border: none;
            background: transparent;
        }}
        QComboBox::down-arrow, QDateEdit::down-arrow {{
            image: url({seta_baixo});
            width: 16px;
            height: 16px;
        }}
        QAbstractSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 26px;
            border: none;
            background: transparent;
        }}
        QAbstractSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 26px;
            border: none;
            background: transparent;
        }}
        QAbstractSpinBox::up-arrow {{
            image: url({seta_cima});
            width: 12px;
            height: 12px;
        }}
        QAbstractSpinBox::down-arrow {{
            image: url({seta_baixo});
            width: 12px;
            height: 12px;
        }}
    """)

    teclado.instalar(app)

    return familia_fonte
