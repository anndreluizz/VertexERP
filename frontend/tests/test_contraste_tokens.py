"""Contraste WCAG AA das cores do design system, nos dois temas."""
import pytest

from design import tokens


def _lum(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _razao(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# (primeiro plano, fundo, minimo): 4,5 texto normal; 3 componente de interface
PARES = [
    ("TEXTO", "CARD", 4.5),
    ("TEXTO", "FUNDO", 4.5),
    ("TEXTO_SECUNDARIO", "CARD", 4.5),
    ("TEXTO_TERCIARIO", "CARD", 4.5),
    ("TEXTO_TERCIARIO", "FUNDO", 4.5),
    ("TEXTO_SOBRE_COR", "PRIMARIA", 4.5),
    ("TEXTO_SOBRE_COR", "SECUNDARIA", 4.5),
    ("TEXTO_SOBRE_COR", "SUCESSO", 4.5),
    ("TEXTO_SOBRE_COR", "ERRO", 4.5),
    ("TEXTO_SOBRE_COR", "ALERTA", 4.5),
    ("SUCESSO", "SUCESSO_CLARO", 4.5),
    ("ALERTA_TEXTO", "ALERTA_CLARO", 4.5),
    ("ERRO", "ERRO_CLARO", 4.5),
    ("PRIMARIA", "CARD", 4.5),
    ("TEXTO_SIDEBAR", "SIDEBAR", 4.5),
    ("BORDA_CAMPO", "CARD", 3.0),
]


@pytest.mark.parametrize("escuro", [False, True])
def test_contraste_minimo(escuro):
    tokens.aplicar(escuro)
    try:
        falhas = [
            f"{a} sobre {b}: {_razao(getattr(tokens, a), getattr(tokens, b)):.2f} < {minimo}"
            for a, b, minimo in PARES
            if _razao(getattr(tokens, a), getattr(tokens, b)) < minimo
        ]
    finally:
        tokens.aplicar(False)
    assert not falhas, falhas
