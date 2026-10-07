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

# quem quita as compras, em média, em até tantos dias é "bom pagador";
# acima disso, "paga com atraso"
PRAZO_BOM_PAGADOR_DIAS = 30

_EPSILON = 0.009  # mesmo limiar de "zero" já usado no resto do projeto


def _parse_data(valor):

    if not valor:
        return None

    texto = str(valor).replace("T", " ")

    try:
        return datetime.fromisoformat(texto[:19])
    except Exception:
        return None


def _fifo_pagamentos(compras, pagamentos):
    """Abate cada pagamento das compras mais antigas primeiro (como
    um caderno de fiado). Devolve (data da compra mais antiga ainda
    em aberto ou None, prazo médio em dias que o cliente leva pra
    quitar, ponderado pelo valor, ou None se nunca quitou nada)."""

    def _ordenados(movs):
        return sorted(
            (
                (d, float(m.get("valor", 0) or 0))
                for m in movs
                if (d := _parse_data(m.get("data")))
            ),
            key=lambda x: x[0],
        )

    abertas = [[d, v] for d, v in _ordenados(compras)]
    soma_valor = soma_valor_dias = 0.0
    i = 0

    for data_pag, valor in _ordenados(pagamentos):
        while valor > _EPSILON and i < len(abertas):
            data_compra, resto = abertas[i]
            abatido = min(resto, valor)
            soma_valor += abatido
            soma_valor_dias += abatido * max((data_pag - data_compra).days, 0)
            abertas[i][1] -= abatido
            valor -= abatido
            if abertas[i][1] <= _EPSILON:
                i += 1

    mais_antiga = abertas[i][0] if i < len(abertas) else None
    prazo_medio = round(soma_valor_dias / soma_valor) if soma_valor else None
    return mais_antiga, prazo_medio


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
        """Nunca negativo -- uma compra/pagamento/cadastro datado no
        futuro (ex.: engano no seletor de data) não pode virar "-28
        dias" na tela; o mais próximo que existe de sentido nesse caso
        é tratar como "hoje" (0 dias)."""

        if not data:
            return None

        return max((agora - data).days, 0)

    criado_em = _parse_data(cliente.get("criado_em"))

    compra_em_aberto, prazo_medio = _fifo_pagamentos(compras, pagamentos)

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
        # idade da compra mais antiga ainda não paga -- é isso que mede
        # atraso (a última movimentação engana: quem compra toda semana
        # e nunca paga, ou paga R$5 de vez em quando, parecia "em dia")
        "dias_em_atraso": (
            _dias_ate_agora(compra_em_aberto)
            if saldo_devedor > _EPSILON else None
        ),
        "prazo_medio_pagamento": prazo_medio,
    }


# ==================================================
# CLASSIFICAÇÃO (usada pelos filtros, KPIs e ficha)
# ==================================================


def eh_ativo(agr):
    """Comprou ou pagou algo nos últimos 90 dias."""
    dias = agr["dias_sem_movimentacao"]
    return dias is not None and dias <= LIMITE_ATIVO_DIAS


def eh_sem_movimento(agr, prazo_dias=PRAZO_INADIMPLENCIA_PADRAO):
    """Sem compra e sem pagamento há mais de 90 dias -- inclui quem
    nunca teve nenhuma movimentação. Não conta quem já é inadimplente:
    esse cliente tem categoria própria (mais urgente) e não deve
    aparecer misturado em "Sem Movimento"."""
    return not eh_ativo(agr) and not eh_inadimplente(agr, prazo_dias)


def eh_inadimplente(agr, prazo_dias=PRAZO_INADIMPLENCIA_PADRAO):
    """Tem compra em aberto mais velha que o prazo configurado
    (30/60/90 dias)."""
    dias = agr.get("dias_em_atraso")
    return dias is not None and dias > prazo_dias


def eh_bom_pagador(agr, prazo_dias=PRAZO_INADIMPLENCIA_PADRAO):
    """Já quitou compras antes, costuma quitar rápido e não tem nada
    velho em aberto agora. Sem histórico de pagamento não conta --
    ainda não dá pra saber."""
    prazo = agr.get("prazo_medio_pagamento")
    atraso = agr.get("dias_em_atraso")
    return (
        prazo is not None
        and prazo <= PRAZO_BOM_PAGADOR_DIAS
        and (atraso is None or atraso <= PRAZO_BOM_PAGADOR_DIAS)
        and not eh_inadimplente(agr, prazo_dias)
    )


def paga_com_atraso(agr, prazo_dias=PRAZO_INADIMPLENCIA_PADRAO):
    """Paga, mas costuma demorar mais que o prazo de bom pagador --
    ainda não é inadimplente, mas merece atenção antes de vender mais
    fiado."""
    prazo = agr.get("prazo_medio_pagamento")
    return (
        prazo is not None
        and prazo > PRAZO_BOM_PAGADOR_DIAS
        and not eh_inadimplente(agr, prazo_dias)
    )


def eh_em_dia(agr):
    """Sem saldo devedor nenhum."""
    return agr["saldo_devedor"] <= _EPSILON


def eh_novo(agr):
    """Cadastro feito há 30 dias ou menos."""
    dias = agr["dias_desde_cadastro"]
    return dias is not None and dias <= LIMITE_NOVO_DIAS


def selo_pagador(agr, prazo_dias=PRAZO_INADIMPLENCIA_PADRAO):
    """(texto, variante do Badge) do selinho ao lado do nome nas listas,
    ou None quando não há nada a destacar. "★" e não emoji: emoji nem
    sempre renderiza no Windows da loja."""
    if not agr:
        return None
    if eh_bom_pagador(agr, prazo_dias):
        return "★ Bom pagador", "sucesso"
    if paga_com_atraso(agr, prazo_dias):
        return "Paga com atraso", "alerta"
    return None


def status_financeiro(agr, prazo_dias=PRAZO_INADIMPLENCIA_PADRAO):
    if eh_inadimplente(agr, prazo_dias):
        return "Inadimplente"
    if eh_bom_pagador(agr, prazo_dias):
        return "Bom Pagador"
    if paga_com_atraso(agr, prazo_dias):
        return "Paga com Atraso"
    return "Em Dia"


def status_relacionamento(agr):
    if eh_novo(agr):
        return "Novo"
    return "Ativo" if eh_ativo(agr) else "Sem Movimento"


def calcular_aviso(agr, prazo_dias=PRAZO_INADIMPLENCIA_PADRAO):
    """Aviso colorido de uma linha só, pra chamar atenção na hora --
    prioridade: inadimplente (mais urgente) > sem movimento > ativo."""

    if eh_inadimplente(agr, prazo_dias):
        return (
            f"🔴 Cliente inadimplente · compra em aberto há "
            f"{agr['dias_em_atraso']} dias"
        )
    if paga_com_atraso(agr, prazo_dias):
        return (
            f"🟡 Costuma pagar com atraso · leva em média "
            f"{agr['prazo_medio_pagamento']} dias pra quitar"
        )
    if eh_sem_movimento(agr, prazo_dias):
        return "🟡 Cliente sem movimentação"
    return "🟢 Cliente Ativo"


def calcular_pontuacao(agr, prazo_dias=PRAZO_INADIMPLENCIA_PADRAO):
    """Substitui o antigo "Saldo Devedor" cru por uma classificação que
    já cruza frequência de compras + atividade recente + inadimplência
    -- pensada pra fazer o gerente bater o olho e já saber quem merece
    atenção, sem precisar fazer conta nenhuma. Critérios (nessa ordem
    de prioridade):

    1. Inadimplente: compra em aberto mais velha que o prazo.
    2. Sem Movimento: nenhuma compra/pagamento nos últimos 90 dias
       (mesmo sem dívida).
    3. Paga com Atraso: quita, mas leva mais de 30 dias em média.
    4. Excelente: 5 compras ou mais, ativo e bom pagador.
    5. Frequente: 2 compras ou mais e ativo (inclui quem tem 5+ mas
       ainda não tem histórico de pagamento).
    6. Ocasional: 0 ou 1 compra e ativo (inclui cliente novo ainda sem
       histórico suficiente pra virar "frequente")."""

    if eh_inadimplente(agr, prazo_dias):
        return "🔴 Cliente Inadimplente"

    if eh_sem_movimento(agr, prazo_dias):
        return "🟠 Cliente Sem Movimento"

    if paga_com_atraso(agr, prazo_dias):
        return "🟠 Cliente Paga com Atraso"

    if agr["qtd_compras"] >= 5 and eh_bom_pagador(agr, prazo_dias):
        return "🟢 Cliente Excelente"

    if agr["qtd_compras"] >= 2:
        return "🔵 Cliente Frequente"

    return "🟡 Cliente Ocasional"
