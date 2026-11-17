"""Primeiro acesso (telas/cadastro_inicial.py): o que vai pro servidor em cada caso."""
import pytest

from design.login_visual import D, forca
from telas.cadastro_inicial import _dados_finais, _erro_email, _erro_senha


@pytest.fixture(autouse=True)
def _limpa():
    D.clear()
    yield
    D.clear()


def test_dados_finais_so_manda_o_que_foi_preenchido():
    assert _dados_finais(True) == {}
    D.update(tel=" (65) 99912-3045 ", loja="Papelaria da Ana com um nome bem comprido", pix="123")
    assert _dados_finais(False) == {"telefone": "(65) 99912-3045"}
    d = _dados_finais(True)
    assert d["pix_chave"] == "123" and len(d["pix_nome"]) == 25  # QR do Pix: nome ate 25


def test_validacoes_das_etapas():
    assert _erro_email("voce@loja.com") is None
    assert _erro_email("voce@loja") and _erro_email("voceloja.com")
    assert _erro_senha("12345") and _erro_senha("123456") is None
    assert forca("")[0] == 0 and forca("Segredo12!")[0] == 4
