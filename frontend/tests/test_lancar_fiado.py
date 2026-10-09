"""Janela Lançar Fiado (ficha do cliente): quantidade x valor unitário
e "Compra fiada" registrada como venda; "Dívida anterior" só fiado."""
from unittest import mock

from telas.ficha_cliente import LancarFiadoDialog
from telas.vendas import Vendas
from services import api


class _Resposta:
    status_code = 200

    def json(self):
        return {}


_CLIENTE = {"id": 3, "nome": "BERNAZIO", "limite_credito": None}


def _enviar(dialogo, esperar_threads):
    with mock.patch(
        "telas.ficha_cliente.lancar_fiado_manual", return_value=_Resposta()
    ) as lancar:
        dialogo.confirmar()
        esperar_threads(dialogo)
    return lancar


def test_quantidade_vezes_valor_unitario(_qapp, esperar_threads):
    dialogo = LancarFiadoDialog(_CLIENTE, 58.98)
    dialogo.valor.setText("13,99")
    dialogo.quantidade.setValue(3)
    dialogo.itens.setText("CALCINHA")

    assert dialogo.lbl_total_compra.text() == "Total da compra: R$ 41,97"
    assert dialogo.lbl_preview_novo_saldo.text() == "R$ 100,95"

    lancar = _enviar(dialogo, esperar_threads)

    cliente_id, valor, descricao, _data = lancar.call_args.args
    assert valor == 41.97
    assert descricao == "3x CALCINHA"
    assert lancar.call_args.kwargs["registrar_venda"] is True


def test_quantidade_um_mantem_a_descricao(_qapp, esperar_threads):
    dialogo = LancarFiadoDialog(_CLIENTE, 0)
    dialogo.valor.setText("13,99")
    dialogo.itens.setText("CALCINHA")

    lancar = _enviar(dialogo, esperar_threads)

    assert lancar.call_args.args[1:3] == (13.99, "CALCINHA")


def test_divida_anterior_esconde_quantidade_e_nao_vira_venda(_qapp, esperar_threads):
    dialogo = LancarFiadoDialog(_CLIENTE, 0)
    dialogo.quantidade.setValue(4)
    dialogo._selecionar_tipo_registro("divida")
    dialogo.valor.setText("200,00")
    dialogo.itens.setText("caderno de janeiro")

    assert dialogo.quantidade.isHidden()
    assert dialogo.lbl_valor_titulo.text() == "Valor da dívida (R$)"
    assert "não conta" in dialogo.lbl_banner_info.text()

    lancar = _enviar(dialogo, esperar_threads)

    # quantidade escondida não multiplica a dívida
    assert lancar.call_args.args[1:3] == (200.0, "caderno de janeiro")
    assert lancar.call_args.kwargs["registrar_venda"] is False


def test_venda_lancada_pela_ficha_aparece_no_detalhe_de_vendas(_qapp, monkeypatch):
    monkeypatch.setattr(api, "_INFO_USUARIO_CACHE", {"admin": True})
    tela = Vendas()
    venda = {
        "id": 20, "data": "2026-10-09T15:00:00", "cliente_id": 3,
        "cliente_nome": "BERNAZIO", "usuario_id": 1, "usuario_nome": "Ana",
        "forma_pagamento": "PRAZO", "forma_pagamento_2": None,
        "valor_total": 41.97, "status": "FINALIZADA", "observacao": "3x CALCINHA",
        "itens": [],
    }
    tela.devolucoes_atual = []

    tela._mostrar_detalhe(venda)

    assert "Lançada pela ficha" in tela.lbl_detalhe_info.text()
    assert tela.tabela_itens.rowCount() == 1
    assert tela.tabela_itens.item(0, 0).text() == "3x CALCINHA"
    assert tela.bt_cancelar.isEnabled()
    assert not tela.bt_devolver.isEnabled()  # sem peças cadastradas
