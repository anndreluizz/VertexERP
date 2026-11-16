"""Produto vendido sem custo cadastrado: o "lucro" viraria o faturamento
inteiro. Visao Geral e Inicio devem tratar como desconhecido."""
from datetime import datetime
from types import SimpleNamespace

from telas.visao_geral import VisaoGeral

PRODUTOS = [{"id": 1, "preco_custo": 4}, {"id": 2, "preco_custo": 0}]


def _venda(produto_id):
    return {
        "data": datetime.now().isoformat(),
        "valor_total": 10,
        "itens": [{"produto_id": produto_id, "quantidade": 1, "valor_unitario": 10}],
    }


def test_visao_geral_custo_desconhecido_quando_falta_custo():
    tela = SimpleNamespace(produtos=PRODUTOS)
    assert VisaoGeral._custo_produtos_vendidos(tela, [_venda(1)]) == 4
    assert VisaoGeral._custo_produtos_vendidos(tela, [_venda(1), _venda(2)]) is None


def test_totais_do_periodo_por_dia_e_por_hora():
    from datetime import date
    v = [{"data": "2026-11-02T10:00:00", "valor_total": 10}, {"data": "2026-11-02T15:00:00", "valor_total": 5}]
    rot, tot = VisaoGeral._totais_do_periodo(v, date(2026, 11, 1), date(2026, 11, 3))
    assert rot == ["01/11", "02/11", "03/11"] and tot == [0, 15, 0]
    rot, tot = VisaoGeral._totais_do_periodo(v, date(2026, 11, 2), date(2026, 11, 2))
    assert len(tot) == 24 and tot[10] == 10 and tot[15] == 5
