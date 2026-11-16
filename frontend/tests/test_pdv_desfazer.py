"""PDV: Desfazer último (item novo sai, item repetido volta uma leitura) e a
barra do limite de crédito no cartão do cliente."""
from tests.test_pdv import _tela_pdv


def _produto(i=1, estoque=50):
    return {"id": i, "codigo": f"P{i}", "nome": f"Produto {i}", "preco": 10, "unidade": "UN", "estoque": estoque}


def test_desfazer_tira_o_item_novo(_qapp):
    t = _tela_pdv()
    t.adicionar_produto_ao_carrinho(_produto(1), 1)
    t.adicionar_produto_ao_carrinho(_produto(2), 1)
    assert t.bt_desfazer.isEnabled()
    t.desfazer_ultimo()
    assert [i["id"] for i in t.itens] == [1]


def test_desfazer_item_repetido_volta_uma_leitura(_qapp):
    t = _tela_pdv()
    t.adicionar_produto_ao_carrinho(_produto(1), 1)
    t.adicionar_produto_ao_carrinho(_produto(1), 1)
    assert t.itens[0]["quantidade"] == 2
    t.desfazer_ultimo()
    assert t.itens[0]["quantidade"] == 1


def test_desfazer_so_vale_uma_vez_e_o_botao_apaga(_qapp):
    t = _tela_pdv()
    t.adicionar_produto_ao_carrinho(_produto(1), 1)
    t.desfazer_ultimo()
    assert not t.itens and not t.bt_desfazer.isEnabled()
    t.desfazer_ultimo()  # nada a desfazer: não quebra
    assert not t.itens


def test_barra_do_limite_mostra_quanto_do_credito_foi_usado(_qapp):
    t = _tela_pdv()
    cli = {"id": 1, "nome": "Maria Souza", "limite_credito": 500, "_agr": {"saldo_devedor": 125}}
    t.definir_cliente(cli)
    assert not t.barra_limite_cliente.isHidden()
    assert t.barra_limite_cliente._pct == 25
    t.definir_cliente({"id": 2, "nome": "Sem Limite", "_agr": {"saldo_devedor": 50}})
    assert t.barra_limite_cliente.isHidden()
    t.definir_cliente(cli)
    t.limpar_cliente()
    assert t.barra_limite_cliente.isHidden()
