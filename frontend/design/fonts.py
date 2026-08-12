from PySide6.QtGui import QFontDatabase

from design.paths import caminho_asset
from design.tokens import FONTE_FAMILIA_PADRAO


def carregar_fonte_inter():
    """Registra a fonte Inter (variavel, um arquivo so cobre todos os
    pesos) na aplicacao e devolve o nome de familia pra usar no
    stylesheet global. Se o arquivo nao carregar por algum motivo, cai
    de volta pra Segoe UI (ja vem em qualquer Windows) em vez de
    quebrar a aplicacao inteira por causa de uma fonte decorativa."""

    caminho = caminho_asset("fonts", "Inter-Variable.ttf")

    id_fonte = QFontDatabase.addApplicationFont(caminho)

    if id_fonte == -1:
        return FONTE_FAMILIA_PADRAO

    familias = QFontDatabase.applicationFontFamilies(id_fonte)

    return familias[0] if familias else FONTE_FAMILIA_PADRAO
