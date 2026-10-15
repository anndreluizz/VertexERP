"""Produto vendido sem custo cadastrado: o "lucro" viraria o faturamento
inteiro. Visao Geral e Inicio devem tratar como desconhecido."""
from datetime import datetime
from types import SimpleNamespace

from telas.dashboard import Dashboard
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


def test_inicio_marca_o_dia_sem_custo():
    por_id = {p["id"]: p for p in PRODUTOS}
    tela = SimpleNamespace()
    Dashboard._construir_series_diarias(tela, [_venda(1)], por_id)
    assert tela._dias_sem_custo == set()
    Dashboard._construir_series_diarias(tela, [_venda(1), _venda(2)], por_id)
    assert tela._dias_sem_custo == {datetime.now().date()}
