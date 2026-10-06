"""Barra de título do Windows na cor do sistema.

A barra padrão é branca/cinza e destoava do menu lateral azul-escuro.
Em vez de esconder a barra e desenhar uma própria (perde arrastar,
encaixar nas bordas, maximizar com duplo clique...), pede pro próprio
Windows pintar a barra com DwmSetWindowAttribute:
- Windows 11: cor de fundo e do texto da barra;
- Windows 10 (20H1+): só o modo escuro (os atributos de cor não existem
  lá e são ignorados sem erro)."""

import sys

from PySide6.QtGui import QColor

_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36


def _colorref(cor):
    # COLORREF do Windows é 0x00BBGGRR
    c = QColor(cor)
    return c.red() | (c.green() << 8) | (c.blue() << 16)


def pintar_barra_titulo(janela, cor_fundo, cor_texto="#FFFFFF", escura=True):
    """Não faz nada fora do Windows nem se a API não existir."""

    if sys.platform != "win32":
        return

    try:
        import ctypes
        from ctypes import wintypes

        hwnd = wintypes.HWND(int(janela.winId()))
        dwm = ctypes.windll.dwmapi

        def definir(atributo, valor):
            dado = ctypes.c_int(valor)
            dwm.DwmSetWindowAttribute(hwnd, atributo, ctypes.byref(dado), ctypes.sizeof(dado))

        definir(_DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if escura else 0)
        definir(_DWMWA_CAPTION_COLOR, _colorref(cor_fundo))
        definir(_DWMWA_TEXT_COLOR, _colorref(cor_texto))
    except Exception:
        pass
