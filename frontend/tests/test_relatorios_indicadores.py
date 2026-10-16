"""Testes de _buscar_dados_indicadores (aba Indicadores de Relatorios,
Fase 6 Onda 6/7) -- funcao pura de agregacao (roda na worker thread,
sem nenhum widget), mais facil de testar isolada do resto da tela.

O aging de inadimplencia e o limite de credito reaproveitam
cliente_analise (mesma logica da tela de Clientes) -- o foco aqui e'
confirmar que a funcao bucketiza certo, nao redemonstrar
cliente_analise (que ja tem seus proprios testes/uso real alhures)."""
from datetime import datetime, timedelta
from unittest import mock

from telas.relatorios.indicadores import _buscar_dados_indicadores


def _cliente(id_, nome, limite_credito=None):
    return {"id": id_, "nome": nome, "limite_credito": limite_credito}


def _movimento(cliente_id, tipo, valor, dias_atras):
    data = (datetime.now() - timedelta(days=dias_atras)).isoformat()
    return {"cliente_id": cliente_id, "tipo": tipo, "valor": valor, "data": data}


def _rodar(clientes=None, movimentos=None, usuarios=None, lojas=None, **extras):

    patches = {
        "margem_categoria": [],
        "estoque_categoria": [],
        "vendas_dia_semana": [],
        "vendas_dia_semana_hora": [],
        "gasto_compras_mensal": [],
        "ranking_fornecedores": [],
        "prazo_fornecedores": [],
        "categorias_sem_venda": [],
        "listar_clientes": clientes or [],
        "listar_movimentos": movimentos or [],
        "listar_usuarios": usuarios or [],
        "listar_lojas": lojas or [],
        **extras,
    }

    with mock.patch.multiple(
        "telas.relatorios.indicadores",
        **{nome: mock.DEFAULT for nome in patches},
    ) as mocks:
        for nome, valor in patches.items():
            mocks[nome].return_value = valor

        return _buscar_dados_indicadores("2026-01-01", "2026-12-31", None)


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
        # (dentro da faixa 91-120), saldo baixo (< limiar de R$500)
        _movimento(2, "COMPRA", 200, dias_atras=100),
        # cliente 3: saldo devedor, ultima movimentacao ha 200 dias
        # (faixa 180+), saldo alto (>= limiar de R$500)
        _movimento(3, "COMPRA", 600, dias_atras=200),
    ]

    resultado = _rodar(clientes=clientes, movimentos=movimentos)

    assert resultado["total_inadimplentes"] == 2
    assert resultado["aging_inadimplencia"] == {
        "91-120": 1, "121-180": 0, "180+": 1,
    }
    assert resultado["clientes_com_limite"] == 1  # so' o cliente 1
    assert resultado["clientes_sem_limite"] == 2  # None e 0 contam como sem
    assert resultado["inadimplentes_valor_alto"] == 1  # cliente 3 (600)
    assert resultado["inadimplentes_valor_baixo"] == 1  # cliente 2 (200)


def test_agrupa_usuarios_por_loja_e_marca_sem_loja():

    usuarios = [
        {"id": 1, "loja_id": 10},
        {"id": 2, "loja_id": 10},
        {"id": 3, "loja_id": 20},
        {"id": 4, "loja_id": None},
    ]
    lojas = [{"id": 10, "nome": "Matriz"}, {"id": 20, "nome": "Filial Centro"}]

    resultado = _rodar(usuarios=usuarios, lojas=lojas)

    assert resultado["usuarios_por_loja"] == {
        "Matriz": 2, "Filial Centro": 1, "Sem loja definida": 1,
    }


def test_repassa_os_relatorios_agregados_sem_alterar():

    margens = [{"categoria": "Roupa", "receita": 100, "lucro": 50, "margem_pct": 50, "quantidade": 5}]
    estoques = [{"categoria": "Roupa", "quantidade": 10, "valor": 500}]
    dias = [{"dia_semana": "Segunda", "quantidade": 3, "total": 90}]
    gasto_compras = [{"mes": "2026-09", "total": 1000}]
    fornecedores = [{"fornecedor_id": 1, "nome": "Fornecedor X", "quantidade_compras": 2, "total": 300}]
    prazos = [{"fornecedor_id": 1, "nome": "Fornecedor X", "prazo_medio_dias": 30.0, "quantidade_parcelas": 2}]
    categorias_paradas = [{"categoria": "Bolsa", "ultima_venda": None, "dias_sem_venda": None}]
    heatmap = [{"dia_semana": "Segunda", "hora": 14, "quantidade": 1, "total": 30}]

    resultado = _rodar(
        margem_categoria=margens,
        estoque_categoria=estoques,
        vendas_dia_semana=dias,
        vendas_dia_semana_hora=heatmap,
        gasto_compras_mensal=gasto_compras,
        ranking_fornecedores=fornecedores,
        prazo_fornecedores=prazos,
        categorias_sem_venda=categorias_paradas,
    )

    assert resultado["margem_categoria"] == margens
    assert resultado["estoque_categoria"] == estoques
    assert resultado["vendas_dia_semana"] == dias
    assert resultado["heatmap_dia_hora"] == heatmap
    assert resultado["gasto_compras_mensal"] == gasto_compras
    assert resultado["ranking_fornecedores"] == fornecedores
    assert resultado["prazo_fornecedores"] == prazos
    assert resultado["categorias_sem_venda"] == categorias_paradas
    assert resultado["total_inadimplentes"] == 0
