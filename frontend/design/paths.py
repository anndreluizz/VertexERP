import os
import sys


def pasta_assets():
    """Resolve a pasta de assets tanto rodando direto do codigo-fonte
    quanto empacotado pelo PyInstaller (onde os arquivos de dados ficam
    ao lado do executavel, apontados por sys._MEIPASS)."""

    base = getattr(
        sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    return os.path.join(base, "assets")


def caminho_asset(*partes):
    return os.path.join(pasta_assets(), *partes)
