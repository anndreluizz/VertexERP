"""Classificação inteligente de clientes -- tudo calculado na hora a
partir do histórico real (movimentos_fiado + criado_em), nunca
guardado em lugar nenhum, pro mesmo espírito do resto do app (Ticket
Médio, "última movimentação há X dias" etc.): nunca fica desatualizado
porque não existe cache pra atualizar.

Usado tanto pela lista de Clientes (filtros/ordenação/KPIs) quanto
pela ficha do cliente (campos e aviso) -- um lugar só pra essa regra,
pra nunca divergir entre as duas telas.
"""

from datetime import datetime

# clientes sem nenhuma movimentação (compra ou pagamento) há mais de
# tantos dias contam como "sem movimento" / não-ativos
LIMITE_ATIVO_DIAS = 90

# cadastro feito há menos de tantos dias conta como "novo"
LIMITE_NOVO_DIAS = 30

# prazos de inadimplência que o gerente pode escolher (a tela usa um
# combo com essas 3 opções; 90 é o padrão)
PRAZOS_INADIMPLENCIA = [30, 60, 90]
PRAZO_INADIMPLENCIA_PADRAO = 90

_EPSILON = 0.009  # mesmo limiar de "zero" já usado no resto do projeto


def _parse_data(valor):

    if not valor:
        return None

    texto = str(valor).replace("T", " ")

    try:
        return datetime.fromisoformat(texto[:19])
    except Exception:
        return None


def calcular_agregados(cliente, movimentos_do_cliente):
    """Uma "ficha resumida" do relacionamento com o cliente, calculada
    a partir dos movimentos de fiado dele (compra/pagamento) e do
    criado_em do cadastro."""

    compras = [m for m in movimentos_do_cliente if m.get("tipo") == "COMPRA"]
    pagamentos = [
        m for m in movimentos_do_cliente if m.get("tipo") == "PAGAMENTO"
    ]

    saldo_devedor = sum(
        float(m.get("valor", 0) or 0) for m in compras
    ) - sum(
        float(m.get("valor", 0) or 0) for m in pagamentos
    )

    datas_compra = [
        d for d in (_parse_data(m.get("data")) for m in compras) if d
    ]
    datas_pagamento = [
        d for d in (_parse_data(m.get("data")) for m in pagamentos) if d
    ]
    datas_todas = datas_compra + datas_pagamento

    ultima_compra = max(datas_compra) if datas_compra else None
    ultimo_pagamento = max(datas_pagamento) if datas_pagamento else None
    ultima_movimentacao = max(datas_todas) if datas_todas else None

    agora = datetime.now()

    def _dias_ate_agora(data):
        return (agora - data).days if data else None

    criado_em = _parse_data(cliente.get("criado_em"))

    return {
        "saldo_devedor": saldo_devedor,
        "qtd_compras": len(compras),
        "maior_compra": max(
            (float(m.get("valor", 0) or 0) for m in compras), default=0.0
        ),
        "total_comprado": sum(
            float(m.get("valor", 0) or 0) for m in compras
        ),
        "ultima_compra": ultima_compra,
        "ultimo_pagamento": ultimo_pagamento,
        "ultima_movimentacao": ultima_movimentacao,
        "criado_em": criado_em,
        "dias_desde_ultima_compra": _dias_ate_agora(ultima_compra),
        "dias_desde_ultimo_pagamento": _dias_ate_agora(ultimo_pagamento),
        "dias_sem_movimentacao": _dias_ate_agora(ultima_movimentacao),
        "dias_desde_cadastro": _dias_ate_agora(criado_em),
    }


# ==================================================
# CLASSIFICAÇÃO (usada pelos filtros, KPIs e ficha)
# ==================================================


def eh_ativo(agr):
    """Comprou ou pagou algo nos últimos 90 dias."""
    dias = agr["dias_sem_movimentacao"]
    return dias is not None and dias <= LIMITE_ATIVO_DIAS


def eh_sem_movimento(agr):
    """Sem compra e sem pagamento há mais de 90 dias -- inclui quem
    nunca teve nenhuma movimentação."""
    return not eh_ativo(agr)


def eh_inadimplente(agr, prazo_dias=PRAZO_INADIMPLENCIA_PADRAO):
    """Tem saldo devedor E a última movimentação já passou do prazo
    configurado (30/60/90 dias)."""
    dias = agr["dias_sem_movimentacao"]
    return (
        agr["saldo_devedor"] > _EPSILON
        and dias is not None
        and dias > prazo_dias
    )


def eh_em_dia(agr):
    """Sem saldo devedor nenhum."""
    return agr["saldo_devedor"] <= _EPSILON


def eh_novo(agr):
    """Cadastro feito há 30 dias ou menos."""
    dias = agr["dias_desde_cadastro"]
    return dias is not None and dias <= LIMITE_NOVO_DIAS


def status_financeiro(agr, prazo_dias=PRAZO_INADIMPLENCIA_PADRAO):
    return "Inadimplente" if eh_inadimplente(agr, prazo_dias) else "Em Dia"


def status_relacionamento(agr):
    if eh_novo(agr):
        return "Novo"
    return "Ativo" if eh_ativo(agr) else "Sem Movimento"


def calcular_aviso(agr, prazo_dias=PRAZO_INADIMPLENCIA_PADRAO):
    """Aviso colorido de uma linha só, pra chamar atenção na hora --
    prioridade: inadimplente (mais urgente) > sem movimento > ativo."""

    if eh_inadimplente(agr, prazo_dias):
        return "🔴 Cliente inadimplente"
    if eh_sem_movimento(agr):
        return "🟡 Cliente sem movimentação"
    return "🟢 Cliente Ativo"


def calcular_pontuacao(agr, prazo_dias=PRAZO_INADIMPLENCIA_PADRAO):
    """Substitui o antigo "Saldo Devedor" cru por uma classificação que
    já cruza frequência de compras + atividade recente + inadimplência
    -- pensada pra fazer o gerente bater o olho e já saber quem merece
    atenção, sem precisar fazer conta nenhuma. Critérios (nessa ordem
    de prioridade):

    1. Inadimplente: tem saldo devedor além do prazo configurado.
    2. Sem Movimento: nenhuma compra/pagamento nos últimos 90 dias
       (mesmo sem dívida).
    3. Excelente: 5 compras ou mais e ativo.
    4. Frequente: 2 a 4 compras e ativo.
    5. Ocasional: 0 ou 1 compra e ativo (inclui cliente novo ainda sem
       histórico suficiente pra virar "frequente")."""

    if eh_inadimplente(agr, prazo_dias):
        return "🔴 Cliente Inadimplente"

    if eh_sem_movimento(agr):
        return "🟠 Cliente Sem Movimento"

    if agr["qtd_compras"] >= 5:
        return "🟢 Cliente Excelente"

    if agr["qtd_compras"] >= 2:
        return "🔵 Cliente Frequente"

    return "🟡 Cliente Ocasional"
