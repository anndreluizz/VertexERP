"""Ajuste de Estoque e Transferencia entre Lojas: mesma estrutura de pagina
(voltar + formulario + historico) e os campos que a logica usa continuam."""
from unittest import mock

import pytest

from telas import ajuste_estoque, transferencia_estoque


@pytest.fixture
def paginas(_qapp, monkeypatch):
    for modulo in (ajuste_estoque, transferencia_estoque):
        monkeypatch.setattr(modulo, "rodar_em_thread", lambda *a, **k: None)
    with mock.patch("services.preferencias_service.carregar", return_value={}):
        return ajuste_estoque.AjusteEstoque(), transferencia_estoque.TransferenciaEstoque()


def test_campos_que_a_logica_usa_existem(paginas):
    for pagina in paginas:
        for nome in ("produto", "bt_produto", "quantidade", "motivo", "tabela"):
            assert hasattr(pagina, nome), nome
    ajuste, transferencia = paginas
    assert ajuste.tipo.count() == 2 and hasattr(ajuste, "bt_registrar")
    assert hasattr(transferencia, "loja_destino") and hasattr(transferencia, "bt_transferir")


def test_voltar_emite_o_sinal(paginas):
    for pagina in paginas:
        recebido = []
        pagina.voltar.connect(lambda: recebido.append(1))
        pagina.bt_voltar.click()
        assert recebido == [1]


def test_ajuste_define_produto_pelo_atalho_da_ficha(paginas):
    ajuste, _ = paginas
    ajuste.definir_produto({"id": 7, "nome": "MOCHILA", "estoque": 4})
    assert ajuste.produto_id == 7
    assert "MOCHILA" in ajuste.produto.text() and "4" in ajuste.produto.text()
