"""Peças compartilhadas das páginas Ajuste de Estoque e Transferência entre
Lojas: mesmo cabeçalho das outras páginas (voltar + ícone + título), um
cartão com o formulário e outro com o histórico."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import BotaoSecundario, BotaoSucesso, CampoTexto, Card, campo_rotulado
from widgets.tables.standard_table import StandardTable


def estilo_combo():
    """Combo de formulário com a mesma cara do CampoTexto."""
    return f"""
        QComboBox {{
            border: 1.5px solid {tokens.BORDA_CAMPO};
            border-radius: {tokens.RADIUS_SM}px;
            padding: 0 12px;
            font-size: {tokens.TAMANHO_MD}px;
            color: {tokens.TEXTO};
            background: {tokens.CARD};
        }}
        QComboBox:focus {{ border-color: {tokens.PRIMARIA}; }}
    """


def _titulo_cartao(texto, subtexto=None):
    caixa = QVBoxLayout()
    caixa.setSpacing(2)
    lbl = QLabel(texto)
    lbl.setStyleSheet(f"""
        background:transparent; color:{tokens.TEXTO};
        font-size:{tokens.TAMANHO_MD}px; font-weight:800;
    """)
    caixa.addWidget(lbl)
    if subtexto:
        sub = QLabel(subtexto)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        caixa.addWidget(sub)
    return caixa


def montar_pagina_movimento(
    pagina, *, icone_nome, titulo, subtitulo, titulo_formulario,
    rotulo_extra, widget_extra, rotulo_acao, rotulo_quantidade_dica,
    placeholder_motivo, titulo_historico, colunas,
):
    """Monta a página em `pagina` (QWidget com o sinal `voltar`) e deixa nela
    os campos que a lógica de cada tela já usa: produto, bt_produto,
    quantidade, motivo, tabela. Devolve o botão da ação principal."""

    pagina.setStyleSheet(f"background:{tokens.FUNDO};")

    layout = QVBoxLayout(pagina)
    layout.setContentsMargins(28, 20, 28, 20)
    layout.setSpacing(16)

    # ---------- cabeçalho ----------
    cabecalho = QHBoxLayout()
    cabecalho.setSpacing(12)

    bt_voltar = pagina.bt_voltar = QPushButton()
    bt_voltar.setFixedSize(36, 36)
    bt_voltar.setCursor(Qt.PointingHandCursor)
    bt_voltar.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
    bt_voltar.setToolTip("Voltar")
    bt_voltar.setAccessibleName("Voltar")
    bt_voltar.setStyleSheet(f"""
        QPushButton {{
            background:{tokens.CARD}; border:1px solid {tokens.BORDA};
            border-radius:{tokens.RADIUS_SM}px;
        }}
        QPushButton:hover {{ background:{tokens.FUNDO}; }}
    """)
    bt_voltar.clicked.connect(pagina.voltar.emit)

    chip = QLabel()
    chip.setFixedSize(36, 36)
    chip.setAlignment(Qt.AlignCenter)
    chip.setStyleSheet(f"background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_SM}px;")
    chip.setPixmap(icone_pixmap(icone_nome, cor=tokens.PRIMARIA, tamanho=18))

    col = QVBoxLayout()
    col.setSpacing(0)
    lbl_titulo = QLabel(titulo)
    lbl_titulo.setStyleSheet(f"""
        background:transparent; font-size:{tokens.TAMANHO_LG}px;
        font-weight:800; color:{tokens.TEXTO};
    """)
    lbl_sub = QLabel(subtitulo)
    lbl_sub.setStyleSheet(f"""
        background:transparent; font-size:{tokens.TAMANHO_XS}px; color:{tokens.TEXTO_TERCIARIO};
    """)
    col.addWidget(lbl_titulo)
    col.addWidget(lbl_sub)

    cabecalho.addWidget(bt_voltar)
    cabecalho.addWidget(chip)
    cabecalho.addLayout(col)
    cabecalho.addStretch()
    layout.addLayout(cabecalho)

    # ---------- formulário ----------
    cartao = Card()
    corpo = QVBoxLayout(cartao)
    corpo.setContentsMargins(22, 18, 22, 20)
    corpo.setSpacing(16)
    corpo.addLayout(_titulo_cartao(titulo_formulario))

    pagina.produto = CampoTexto("Escolha o produto…")
    pagina.produto.setReadOnly(True)
    pagina.bt_produto = BotaoSecundario("Escolher produto", icone_nome="search")
    pagina.bt_produto.setMinimumHeight(44)
    linha_produto = QWidget()
    linha_produto.setStyleSheet("background:transparent;")
    lp = QHBoxLayout(linha_produto)
    lp.setContentsMargins(0, 0, 0, 0)
    lp.setSpacing(10)
    lp.addWidget(pagina.produto, 1)
    lp.addWidget(pagina.bt_produto)
    corpo.addWidget(campo_rotulado("Produto", linha_produto))

    pagina.quantidade = CampoTexto("0")
    pagina.motivo = CampoTexto(placeholder_motivo)

    linha = QHBoxLayout()
    linha.setSpacing(16)
    bloco_extra = campo_rotulado(rotulo_extra, widget_extra)
    bloco_qtd = campo_rotulado("Quantidade", pagina.quantidade, rotulo_quantidade_dica)
    bloco_motivo = campo_rotulado("Motivo", pagina.motivo)
    linha.addWidget(bloco_extra, 2)
    linha.addWidget(bloco_qtd, 1)
    linha.addWidget(bloco_motivo, 3)
    corpo.addLayout(linha)

    rodape = QHBoxLayout()
    rodape.addStretch()
    acao = BotaoSucesso(rotulo_acao, icone_nome="check")
    acao.setMinimumHeight(44)
    acao.setMinimumWidth(190)
    rodape.addWidget(acao)
    corpo.addLayout(rodape)

    layout.addWidget(cartao)

    # ---------- histórico ----------
    # sem sombra: o cartão envolve uma lista que pode crescer
    historico = Card(sombra=False)
    h = QVBoxLayout(historico)
    h.setContentsMargins(22, 18, 22, 18)
    h.setSpacing(12)
    h.addLayout(_titulo_cartao(titulo_historico))
    pagina.tabela = StandardTable(colunas)
    h.addWidget(pagina.tabela, 1)
    layout.addWidget(historico, 1)

    return acao
