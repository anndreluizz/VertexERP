"""Extrato do WhatsApp: compras com data, produtos e preco; depois de um
pagamento, so' as compras feitas depois dele."""
from telas.ficha_cliente.whatsapp import montar_extrato_whatsapp

ITENS = {1: "MALBEC x1 — R$ 189,99", 2: "HIDRATANTE x2 — R$ 40,00\nSABONETE x1 — R$ 10,00"}


def _texto(movimentos, saldo=0):
    return montar_extrato_whatsapp("Ana", "3.L.A", movimentos, lambda m: ITENS.get(m.get("venda_id"), ""), saldo)


def test_sem_pagamento_lista_todas_as_compras():
    texto = _texto([  # mais novo primeiro
        {"tipo": "COMPRA", "venda_id": 2, "valor": "50", "data": "2026-10-20T10:00:00"},
        {"tipo": "COMPRA", "venda_id": 1, "valor": "189.99", "data": "2026-10-12T09:00:00"},
    ], 239.99)
    assert texto.index("12/10/2026") < texto.index("20/10/2026")
    assert "• MALBEC x1 — R$ 189,99" in texto and "• SABONETE x1 — R$ 10,00" in texto
    assert "Total das compras: R$ 239,99" in texto


def test_depois_do_pagamento_so_as_compras_novas():
    texto = _texto([
        {"tipo": "COMPRA", "venda_id": 2, "valor": "50", "data": "2026-10-20T10:00:00"},
        {"tipo": "PAGAMENTO", "valor": "189.99", "data": "2026-10-15T09:00:00"},
        {"tipo": "COMPRA", "venda_id": 1, "valor": "189.99", "data": "2026-10-12T09:00:00"},
    ], 50)
    assert "MALBEC" not in texto
    assert "HIDRATANTE" in texto
    assert "Último pagamento: R$ 189,99 em 15/10/2026" in texto


def test_pagamento_sem_compra_depois():
    texto = _texto([{"tipo": "PAGAMENTO", "valor": "10", "data": "2026-10-15"}])
    assert "Nenhuma compra depois do último pagamento." in texto
