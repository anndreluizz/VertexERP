"""Compra fiada lançada pela ficha do cliente (registrar_venda=True)
vira venda a prazo sem itens -- conta em Vendas, no total da vendedora
e no faturamento, sem mexer no caixa."""
from datetime import date
from decimal import Decimal


def _lancar(client, auth_headers, cliente, valor="41.97", **extra):
    corpo = {
        "cliente_id": cliente.id,
        "tipo": "COMPRA",
        "valor": valor,
        "descricao": "3x CALCINHA",
    }
    corpo.update(extra)
    return client.post("/fiado/movimentos", json=corpo, headers=auth_headers)


def test_compra_fiada_vira_venda_a_prazo_sem_caixa(client, auth_headers, cliente):
    response = _lancar(client, auth_headers, cliente, registrar_venda=True)

    assert response.status_code == 200, response.text
    venda_id = response.json()["venda_id"]
    assert venda_id is not None

    venda = client.get(f"/vendas/{venda_id}", headers=auth_headers).json()
    assert venda["status"] == "FINALIZADA"
    assert venda["forma_pagamento"] == "PRAZO"
    assert venda["cliente_nome"] == "Cliente Teste"
    assert venda["usuario_nome"] == "Usuário Teste"
    assert venda["observacao"] == "3x CALCINHA"
    assert venda["itens"] == []
    assert Decimal(str(venda["valor_total"])) == Decimal("41.97")

    hoje = date.today().isoformat()
    [linha] = client.get(
        f"/vendas/resumo-vendedores?data_inicio={hoje}&data_fim={hoje}",
        headers=auth_headers,
    ).json()
    assert Decimal(str(linha["total_vendido"])) == Decimal("41.97")

    saldo = client.get(f"/fiado/saldo/{cliente.id}", headers=auth_headers).json()
    assert Decimal(str(saldo["saldo"])) == Decimal("41.97")


def test_divida_anterior_continua_so_fiado(client, auth_headers, cliente):
    response = _lancar(client, auth_headers, cliente)

    assert response.status_code == 200, response.text
    assert response.json()["venda_id"] is None
    assert client.get("/vendas/", headers=auth_headers).json() == []


def test_venda_respeita_a_data_escolhida(client, auth_headers, cliente):
    response = _lancar(
        client, auth_headers, cliente,
        registrar_venda=True, data="2026-10-01T00:00:00",
    )

    venda = client.get(
        f"/vendas/{response.json()['venda_id']}", headers=auth_headers
    ).json()
    assert venda["data"].startswith("2026-10-01")


def test_cancelar_venda_manual_desfaz_o_fiado_sem_caixa_aberto(
    client, auth_headers, cliente
):
    response = _lancar(client, auth_headers, cliente, registrar_venda=True)
    venda_id = response.json()["venda_id"]

    cancelada = client.delete(f"/vendas/{venda_id}", headers=auth_headers)

    assert cancelada.status_code == 200, cancelada.text
    venda = client.get(f"/vendas/{venda_id}", headers=auth_headers).json()
    assert venda["status"] == "CANCELADA"
    saldo = client.get(f"/fiado/saldo/{cliente.id}", headers=auth_headers).json()
    assert Decimal(str(saldo["saldo"])) == Decimal("0")


def test_lancamento_que_virou_venda_so_corrige_cancelando_a_venda(
    client, auth_headers, cliente
):
    response = _lancar(client, auth_headers, cliente, registrar_venda=True)

    apagar = client.delete(
        f"/fiado/movimentos/{response.json()['id']}", headers=auth_headers
    )

    assert apagar.status_code == 400
    assert "cancele a venda" in apagar.json()["detail"]
