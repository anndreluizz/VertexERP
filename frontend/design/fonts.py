from PySide6.QtGui import QFont, QFontDatabase

from design.paths import caminho_asset
from design.tokens import FONTE_FAMILIA_PADRAO


def carregar_fonte_inter():
    """Registra a fonte Inter (variavel, um arquivo so cobre todos os
    pesos) na aplicacao e devolve o nome de familia pra usar no
    stylesheet global. Se o arquivo nao carregar por algum motivo, cai
    de volta pra Segoe UI (ja vem em qualquer Windows) em vez de
    quebrar a aplicacao inteira por causa de uma fonte decorativa."""

    global _familia_carregada, _familia_titulo

    # Vertex 2.0: Figtree no texto e Bricolage Grotesque nos titulos
    # (as do prototipo); Inter fica de reserva se a Figtree falhar
    for arquivo in ("Figtree-Variable.ttf", "Inter-Variable.ttf"):
        familias = _registrar(arquivo)
        if familias:
            _familia_carregada = familias[0]
            break
    else:
        return FONTE_FAMILIA_PADRAO

    titulo = _registrar("BricolageGrotesque-Variable.ttf")
    _familia_titulo = titulo[0] if titulo else _familia_carregada

    return _familia_carregada


def _registrar(arquivo):
    id_fonte = QFontDatabase.addApplicationFont(caminho_asset("fonts", arquivo))
    return QFontDatabase.applicationFontFamilies(id_fonte) if id_fonte != -1 else []


def familia_titulo():
    """Familia dos titulos grandes (Bricolage Grotesque) pra usar em
    stylesheet: f"font-family:'{familia_titulo()}';"."""
    return _familia_titulo


# família que carregar_fonte_inter() conseguiu registrar (Inter), ou o
# fallback -- quem monta QFont em código usa fonte() abaixo em vez de
# QFont(tokens.FONTE_FAMILIA_PADRAO, ...), que travava botões e menu em
# Segoe UI enquanto o resto da tela (stylesheet global) já era Inter
_familia_carregada = FONTE_FAMILIA_PADRAO
_familia_titulo = FONTE_FAMILIA_PADRAO


def fonte(tamanho_px):
    """QFont na família do app com tamanho em PIXELS -- mesma unidade
    dos tokens.TAMANHO_* usados nos stylesheets. QFont(familia, 14) é
    em pontos (~19px numa tela 96dpi), o que deixava botões/combos
    visivelmente maiores que o texto ao redor."""

    f = QFont(_familia_carregada)
    f.setPixelSize(tamanho_px)
    return f
