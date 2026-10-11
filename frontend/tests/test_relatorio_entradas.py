"""Relatorios > Caixa: cards de dinheiro que entrou no periodo."""
from unittest import mock

from telas import relatorios
from services import caixa_service

DADOS = {
    "dinheiro": "140.00", "pix": "100.00", "cartao": "50.00", "outros": "0",
    "fiado_recebido": "100.00", "total": "290.00", "sangrias": "25.00", "vendas_prazo": "80.00",
}


def test_cards_mostram_o_que_entrou(_qapp, monkeypatch):
    monkeypatch.setattr(relatorios, "rodar_em_thread", lambda *a, **k: None)
    tela = relatorios.Relatorios()
    tela._ao_atualizar_entradas(DADOS)

    assert tela.card_entrou_total.lbl_valor.text() == "R$ 290,00"
    assert tela.card_entrou_dinheiro.lbl_valor.text() == "R$ 140,00"
    assert tela.card_entrou_fiado.lbl_valor.text() == "R$ 100,00"
    nota = tela.lbl_entradas_nota.text()
    assert "R$ 25,00" in nota and "R$ 80,00" in nota


def test_service_monta_a_url_com_periodo_e_loja():
    from datetime import date
    resposta = mock.Mock(status_code=200, json=mock.Mock(return_value=DADOS))
    with mock.patch.object(caixa_service, "get", return_value=resposta) as get:
        caixa_service.entradas_caixa(date(2026, 10, 1), date(2026, 10, 11), 2)
    get.assert_called_once_with("/caixa/entradas?inicio=2026-10-01&fim=2026-10-11&loja_id=2")
