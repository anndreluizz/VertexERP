"""Testes de _buscar_dados_indicadores (aba Indicadores de Relatorios,
Fase 6 Onda 6) -- funcao pura de agregacao (roda na worker thread, sem
nenhum widget), mais facil de testar isolada do resto da tela.

O aging de inadimplencia e o limite de credito reaproveitam
cliente_analise (mesma logica da tela de Clientes) -- o foco aqui e'
confirmar que a funcao bucketiza certo, nao redemonstrar
cliente_analise (que ja tem seus proprios testes/uso real alhures)."""
from datetime import datetime, timedelta
from unittest import mock

from telas.relatorios import _buscar_dados_indicadores


def _cliente(id_, nome, limite_credito=None):
    return {"id": id_, "nome": nome, "limite_credito": limite_credito}


def _movimento(cliente_id, tipo, valor, dias_atras):
    data = (datetime.now() - timedelta(days=dias_atras)).isoformat()
    return {"cliente_id": cliente_id, "tipo": tipo, "valor": valor, "data": data}


def test_agrupa_inadimplentes_por_faixa_de_atraso_e_conta_limite_credito():

    clientes = [
        _cliente(1, "Em dia", limite_credito=500),
        _cliente(2, "Inadimplente recente", limite_credito=None),
        _cliente(3, "Inadimplente antigo", limite_credito=0),
    ]

    movimentos = [
        # cliente 1: comprou e pagou, sem saldo -- nao e' inadimplente
        _movimento(1, "COMPRA", 100, dias_atras=10),
        _movimento(1, "PAGAMENTO", 100, dias_atras=5),
        # cliente 2: saldo devedor, ultima movimentacao ha 100 dias
        # (dentro da faixa 91-120)
        _movimento(2, "COMPRA", 200, dias_atras=100),
        # cliente 3: saldo devedor, ultima movimentacao ha 200 dias
        # (faixa 180+)
        _movimento(3, "COMPRA", 300, dias_atras=200),
    ]

    with mock.patch(
        "telas.relatorios.margem_categoria", return_value=[]
    ), mock.patch(
        "telas.relatorios.estoque_categoria", return_value=[]
    ), mock.patch(
        "telas.relatorios.vendas_dia_semana", return_value=[]
    ), mock.patch(
        "telas.relatorios.listar_clientes", return_value=clientes
    ), mock.patch(
        "telas.relatorios.listar_movimentos", return_value=movimentos
    ):
        resultado = _buscar_dados_indicadores("2026-01-01", "2026-12-31", None)

    assert resultado["total_inadimplentes"] == 2
    assert resultado["aging_inadimplencia"] == {
        "91-120": 1, "121-180": 0, "180+": 1,
    }
    assert resultado["clientes_com_limite"] == 1  # so' o cliente 1
    assert resultado["clientes_sem_limite"] == 2  # None e 0 contam como sem


def test_repassa_os_relatorios_agregados_sem_alterar():

    margens = [{"categoria": "Roupa", "receita": 100, "lucro": 50, "margem_pct": 50, "quantidade": 5}]
    estoques = [{"categoria": "Roupa", "quantidade": 10, "valor": 500}]
    dias = [{"dia_semana": "Segunda", "quantidade": 3, "total": 90}]

    with mock.patch(
        "telas.relatorios.margem_categoria", return_value=margens
    ), mock.patch(
        "telas.relatorios.estoque_categoria", return_value=estoques
    ), mock.patch(
        "telas.relatorios.vendas_dia_semana", return_value=dias
    ), mock.patch(
        "telas.relatorios.listar_clientes", return_value=[]
    ), mock.patch(
        "telas.relatorios.listar_movimentos", return_value=[]
    ):
        resultado = _buscar_dados_indicadores(None, "2026-12-31", 1)

    assert resultado["margem_categoria"] == margens
    assert resultado["estoque_categoria"] == estoques
    assert resultado["vendas_dia_semana"] == dias
    assert resultado["total_inadimplentes"] == 0
