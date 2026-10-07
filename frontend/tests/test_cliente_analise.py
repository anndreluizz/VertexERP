"""Regras de classificação de cliente (cliente_analise) -- o atraso é
contado pela compra mais antiga ainda não paga (FIFO), não pela
última movimentação."""
from datetime import datetime, timedelta

from services import cliente_analise as ca


def _mov(tipo, valor, dias_atras):
    data = (datetime.now() - timedelta(days=dias_atras)).isoformat()
    return {"tipo": tipo, "valor": valor, "data": data}


def _agr(*movs):
    return ca.calcular_agregados({}, list(movs))


def test_quem_compra_sempre_e_nunca_paga_e_inadimplente():
    # antes: a compra de ontem "zerava" o atraso e ele nunca aparecia
    agr = _agr(_mov("COMPRA", 100, 120), _mov("COMPRA", 50, 1))
    assert agr["dias_em_atraso"] == 120
    assert ca.eh_inadimplente(agr)


def test_pagamento_parcial_quita_a_compra_mais_antiga_primeiro():
    agr = _agr(
        _mov("COMPRA", 100, 120),
        _mov("COMPRA", 100, 20),
        _mov("PAGAMENTO", 100, 10),  # quita a de 120 dias
    )
    assert agr["dias_em_atraso"] == 20
    assert agr["prazo_medio_pagamento"] == 110
    assert not ca.eh_inadimplente(agr)
    assert ca.paga_com_atraso(agr)


def test_pagamento_simbolico_nao_esconde_divida_velha():
    agr = _agr(_mov("COMPRA", 1000, 150), _mov("PAGAMENTO", 5, 2))
    assert agr["dias_em_atraso"] == 150
    assert ca.eh_inadimplente(agr)


def test_bom_pagador_vira_excelente():
    movs = []
    for i in range(5):
        movs += [_mov("COMPRA", 50, 80 - i * 15), _mov("PAGAMENTO", 50, 75 - i * 15)]
    agr = _agr(*movs)
    assert agr["prazo_medio_pagamento"] == 5
    assert agr["dias_em_atraso"] is None
    assert ca.eh_bom_pagador(agr)
    assert "Excelente" in ca.calcular_pontuacao(agr)
    assert ca.status_financeiro(agr) == "Bom Pagador"


def test_compra_muito_mas_paga_devagar_nao_e_excelente():
    movs = []
    for i in range(5):
        movs += [_mov("COMPRA", 50, 85 - i * 2), _mov("PAGAMENTO", 50, 30 - i * 2)]
    agr = _agr(*movs)
    assert agr["prazo_medio_pagamento"] == 55
    assert not ca.eh_bom_pagador(agr)
    assert "Paga com Atraso" in ca.calcular_pontuacao(agr)


def test_sem_historico_de_pagamento_nao_e_bom_pagador():
    agr = _agr(_mov("COMPRA", 50, 3))
    assert agr["prazo_medio_pagamento"] is None
    assert not ca.eh_bom_pagador(agr)
    assert not ca.eh_inadimplente(agr)


def test_selo_ao_lado_do_nome():
    movs = []
    for i in range(3):
        movs += [_mov("COMPRA", 50, 60 - i * 10), _mov("PAGAMENTO", 50, 58 - i * 10)]
    assert ca.selo_pagador(_agr(*movs)) == ("★ Bom pagador", "sucesso")
    lento = _agr(_mov("COMPRA", 50, 80), _mov("PAGAMENTO", 50, 20))
    assert ca.selo_pagador(lento) == ("Paga com atraso", "alerta")
    assert ca.selo_pagador(_agr(_mov("COMPRA", 50, 3))) is None
    assert ca.selo_pagador({}) is None
