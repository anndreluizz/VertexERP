"""Clientes: card "Recebido de fiado" so' da loja (combo ou terminal)."""
from services import api
from telas import clientes


def _rodar(monkeypatch, loja_combo, loja_terminal, info={"admin": True}):
    monkeypatch.setattr(api, "_INFO_USUARIO_CACHE", info)
    pedidos = []

    def entradas(inicio, fim, loja_id):
        pedidos.append(loja_id)
        return {"fiado_recebido": "30.00"}

    monkeypatch.setattr(clientes, "listar_clientes", lambda loja_id: [])
    monkeypatch.setattr(clientes, "listar_movimentos", lambda: [
        {"cliente_id": 1, "tipo": "PAGAMENTO", "valor": 999},
    ])
    monkeypatch.setattr(clientes, "entradas_caixa", entradas)
    monkeypatch.setattr(clientes, "carregar_loja_id", lambda: loja_terminal)

    recebido = clientes._buscar_dados_clientes(loja_combo)[2]
    return recebido, (pedidos[0] if pedidos else None)


def test_sem_combo_usa_loja_do_terminal(monkeypatch):
    assert _rodar(monkeypatch, None, 2) == (30.0, 2)


def test_combo_escolhido_prevalece(monkeypatch):
    assert _rodar(monkeypatch, 1, 2) == (30.0, 1)


def test_vendedor_carrega_sem_pedir_as_entradas_do_caixa(monkeypatch):
    # 19/10: /caixa/entradas e' 403 pro vendedor e derrubava a tela
    assert _rodar(monkeypatch, None, 2, {"admin": False, "permissoes": []}) == (0.0, None)
