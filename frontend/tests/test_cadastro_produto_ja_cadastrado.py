"""Novo Produto: bipar um codigo que ja' existe oferece somar ao
estoque em vez de deixar cadastrar de novo."""
from unittest import mock

from telas.cadastro_produto import busca_externa
from tests.test_cadastro_produto_enter import _tela

PRODUTO = {"id": 7, "codigo": "0007", "nome": "BOLSA", "estoque": 3}


def test_codigo_ja_cadastrado_vira_entrada_de_estoque(_qapp, monkeypatch):
    with mock.patch.object(busca_externa, "buscar_produto", return_value=PRODUTO):
        assert busca_externa._buscar_produto_externo_com_flag("789", True, True) == (PRODUTO, None, True)

    tela = _tela(monkeypatch)
    tela.codigo_barras.setText("789")
    resposta = mock.Mock(status_code=201)
    with mock.patch.object(busca_externa.api, "usuario_tem_permissao", return_value=True), \
         mock.patch.object(busca_externa.QInputDialog, "getInt", return_value=(5, True)), \
         mock.patch.object(busca_externa.QMessageBox, "information"), \
         mock.patch.object(busca_externa, "ajustar_estoque", return_value=resposta) as ajustar:
        tela._ao_buscar_automatico_sucesso((PRODUTO, None, True))

    assert ajustar.call_args[0][0]["produto_id"] == 7
    assert ajustar.call_args[0][0]["quantidade"] == 5
    assert ajustar.call_args[0][0]["tipo"] == "ENTRADA"
    assert tela.codigo_barras.text() == ""
    tela.close()
