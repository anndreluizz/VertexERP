from PySide6.QtGui import QFont, QFontDatabase

from design.paths import caminho_asset
from design.tokens import FONTE_FAMILIA_PADRAO


def carregar_fonte_inter():
    """Registra a fonte Inter (variavel, um arquivo so cobre todos os
    pesos) na aplicacao e devolve o nome de familia pra usar no
    stylesheet global. Se o arquivo nao carregar por algum motivo, cai
    de volta pra Segoe UI (ja vem em qualquer Windows) em vez de
    quebrar a aplicacao inteira por causa de uma fonte decorativa."""

    caminho = caminho_asset("fonts", "Inter-Variable.ttf")

    global _familia_carregada

    id_fonte = QFontDatabase.addApplicationFont(caminho)

    if id_fonte == -1:
        return FONTE_FAMILIA_PADRAO

    familias = QFontDatabase.applicationFontFamilies(id_fonte)

    if familias:
        _familia_carregada = familias[0]

    return _familia_carregada


# família que carregar_fonte_inter() conseguiu registrar (Inter), ou o
# fallback -- quem monta QFont em código usa fonte() abaixo em vez de
# QFont(tokens.FONTE_FAMILIA_PADRAO, ...), que travava botões e menu em
# Segoe UI enquanto o resto da tela (stylesheet global) já era Inter
_familia_carregada = FONTE_FAMILIA_PADRAO


def fonte(tamanho_px):
    """QFont na família do app com tamanho em PIXELS -- mesma unidade
    dos tokens.TAMANHO_* usados nos stylesheets. QFont(familia, 14) é
    em pontos (~19px numa tela 96dpi), o que deixava botões/combos
    visivelmente maiores que o texto ao redor."""

    f = QFont(_familia_carregada)
    f.setPixelSize(tamanho_px)
    return f
