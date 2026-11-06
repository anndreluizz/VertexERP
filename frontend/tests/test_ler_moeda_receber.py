"""Valor com ponto de milhar nao pode dar 'valor invalido' (bug: devendo
R$ 1.234,50, o campo vinha preenchido assim e o Confirmar recusava)."""
import pytest

from telas.ficha_cliente.registrar_pagamento import texto_resta, valores_rapidos
from telas.pdv.comum import _parse_valor
from utils.formatacao import formatar_moeda, ler_moeda


@pytest.mark.parametrize("texto, esperado", [
    ("1.234,50", 1234.5), ("1234,50", 1234.5), ("R$ 50", 50), ("12.5", 12.5),
    ("1.000", 1000), ("0,99", 0.99), (formatar_moeda(98765.4, com_simbolo=False), 98765.4),
])
def test_ler_moeda(texto, esperado):
    assert ler_moeda(texto) == pytest.approx(esperado)


def test_ler_moeda_invalido_e_pdv_tolerante():
    with pytest.raises(ValueError):
        ler_moeda("abc")
    assert _parse_valor("1.500,00") == 1500
    assert _parse_valor("") == 0


def test_valores_rapidos_e_resta():
    assert valores_rapidos(320)[:2] == [("Tudo (R$ 320,00)", 320), ("Metade", 160)]
    assert ("R$ 100,00", 100) in valores_rapidos(320)
    assert valores_rapidos(0) == []
    assert "fica devendo <b>R$ 220,00</b>" in texto_resta(320, "100,00")
    assert "Quita tudo" in texto_resta(1234.5, "1.234,50")
