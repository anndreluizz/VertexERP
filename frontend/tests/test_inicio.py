"""Início do Vertex 2.0: numeros do dia, vendas por hora e mais vendidos."""
from datetime import date, datetime, timedelta

from telas.inicio import resumo_inicio, saudacao

HOJE = date(2026, 11, 5)  # quinta


def _venda(dia, hora, valor, itens=()):
    return {"status": "FINALIZADA", "valor_total": valor,
            "data": datetime.combine(dia, datetime.min.time()).replace(hour=hora).isoformat(),
            "itens": [{"produto_id": p, "quantidade": q} for p, q in itens]}


def test_resumo_do_dia():
    passada = HOJE - timedelta(days=7)
    vendas = [
        _venda(HOJE, 10, 100, [(1, 2)]), _venda(HOJE, 10, 50, [(2, 1), (1, 1)]),
        _venda(HOJE, 17, 30, [(2, 4)]),
        _venda(passada, 10, 120), _venda(HOJE - timedelta(days=14), 10, 40),
        {"status": "CANCELADA", "valor_total": 999, "data": f"{HOJE}T10:00:00", "itens": []},
    ]
    movs = [{"tipo": "PAGAMENTO", "valor": 60, "data": f"{HOJE}T09:00:00"},
            {"tipo": "PAGAMENTO", "valor": 10, "data": f"{passada}T09:00:00"},
            {"tipo": "COMPRA", "valor": 80, "data": f"{HOJE}T09:00:00"}]
    produtos = {1: {"nome": "Sandália"}, 2: {"nome": "Sabonete"}}
    r = resumo_inicio(vendas, {"vendas_hoje": 180, "vendas_hoje_qtd": 3, "saldo_caixa": 412},
                      movs, produtos, hoje=HOJE)
    assert r["nota_vendas"] == "3 vendas · +50% que quinta passada"
    assert r["ticket"] == 60
    assert r["recebido_fiado"] == 60 and r["pagamentos_fiado"] == 1
    horas = {h: (hoje, media) for h, hoje, media in r["horas"]}
    assert horas[10] == (150, (120 + 40) / 4)
    assert horas[17] == (30, 0)
    assert r["mais_vendidos"] == [("Sabonete", 5), ("Sandália", 3)]


def test_saudacao():
    assert saudacao(datetime(2026, 11, 5, 8)) == "Bom dia"
    assert saudacao(datetime(2026, 11, 5, 14)) == "Boa tarde"
    assert saudacao(datetime(2026, 11, 5, 19)) == "Boa noite"
