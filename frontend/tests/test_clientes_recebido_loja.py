"""Clientes: card "Recebido de fiado" so' da loja (combo ou terminal)."""
from telas import clientes


def _rodar(monkeypatch, loja_combo, loja_terminal):
    pedidos = []

    def entradas(inicio, fim, loja_id):
        pedidos.append(loja_id)
        return {"fiado_recebido": "30.00"}

    monkeypatch.setattr(clientes, "listar_clientes", lambda loja_id: [])
    monkeypatch.setattr(clientes, "listar_movimentos", lambda: [
        {"cliente_id": 1, "tipo": "PAGAMENTO", "valor": 999},
    ])
    monkeypatch.setattr(clientes, "listar_vendas", lambda: [])
    monkeypatch.setattr(clientes, "entradas_caixa", entradas)
    monkeypatch.setattr(clientes, "carregar_loja_id", lambda: loja_terminal)

    recebido = clientes._buscar_dados_clientes(loja_combo)[3]
    return recebido, pedidos[0]


def test_sem_combo_usa_loja_do_terminal(monkeypatch):
    assert _rodar(monkeypatch, None, 2) == (30.0, 2)


def test_combo_escolhido_prevalece(monkeypatch):
    assert _rodar(monkeypatch, 1, 2) == (30.0, 1)
