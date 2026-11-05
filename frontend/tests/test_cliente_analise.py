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


def test_quem_pagou_dentro_do_prazo_nao_e_inadimplente():
    # caso JOSE AZEVEDO: saldo anterior de 93 dias, pagou parte hoje
    agr = _agr(_mov("COMPRA", 450.96, 93), _mov("PAGAMENTO", 150, 0))
    assert agr["dias_em_atraso"] == 93
    assert not ca.eh_inadimplente(agr)
    assert ca.status_financeiro(agr) == "Paga com Atraso"
    # ultimo pagamento tambem velho: volta a ser inadimplente
    assert ca.eh_inadimplente(_agr(_mov("COMPRA", 1000, 200), _mov("PAGAMENTO", 5, 120)))


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
        movs += [_mov("COMPRA", 50, 85 - i * 2), _mov("PAGAMENTO", 50, 15 - i * 2)]
    agr = _agr(*movs)
    assert agr["prazo_medio_pagamento"] == 70
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
    lento = _agr(_mov("COMPRA", 50, 90), _mov("PAGAMENTO", 50, 20))
    assert ca.selo_pagador(lento) == ("Paga com atraso", "alerta")
    assert ca.selo_pagador(_agr(_mov("COMPRA", 50, 3))) is None
    assert ca.selo_pagador({}) is None


def test_haver_e_perda_abatem_a_divida():
    # antes so' PAGAMENTO abatia: haver e divida baixada (PERDA) ficavam
    # contando como "a receber"
    agr = _agr(_mov("COMPRA", 100, 400), _mov("HAVER", 30, 10), _mov("PERDA", 70, 1))
    assert agr["saldo_devedor"] == 0
    assert agr["perdido"] == 70
    assert agr["dias_em_atraso"] is None


def test_negativado_tem_status_proprio_e_nao_ganha_selo():
    # antes a baixa (PERDA) contava como pagamento e o negativado
    # aparecia "Paga com atraso" ou ate' "Bom pagador"
    movs = [_mov("COMPRA", 100, 400), _mov("PERDA", 100, 1)]
    agr = ca.calcular_agregados({"negativado": True}, movs)
    assert agr["prazo_medio_pagamento"] is None
    assert ca.status_financeiro(agr) == "Negativado"
    assert ca.selo_pagador(agr) is None
    assert ca.calcular_pontuacao(agr) == "🔴 Cliente Negativado"


def test_devendo_ha_mais_de_2_meses_sem_pagar_nao_e_em_dia():
    agr = _agr(_mov("COMPRA", 100, 70))
    assert ca.status_financeiro(agr) == "Paga com Atraso"
    assert ca.calcular_aviso(agr) == "🟡 Pagamento atrasado · compra em aberto há 70 dias"
    # ate' 2 meses ainda nao e' atraso (regra do dono, 05/11/2026)
    assert ca.status_financeiro(_agr(_mov("COMPRA", 100, 50))) == "Em Dia"
    quita_em_45 = _agr(_mov("COMPRA", 50, 60), _mov("PAGAMENTO", 50, 15))
    assert ca.status_financeiro(quita_em_45) == "Bom Pagador"
    assert ca.status_financeiro(_agr(_mov("COMPRA", 100, 10))) == "Em Dia"


def test_atrasado_amarelo_entre_2_meses_e_inadimplencia():
    from telas.clientes import _status_cliente
    from telas.selecionar_cliente import situacao_fiado
    cliente = {"nome": "R", "ativo": True}
    agr = _agr(_mov("COMPRA", 320, 75))
    assert ca.atrasado_sem_ser_inadimplente(agr)
    assert _status_cliente(cliente, agr, 90) == ("Atrasado · 75 dias", "alerta")
    assert situacao_fiado({**cliente, "_agr": agr})[:2] == ("Atrasado · 75 dias", "alerta")
    # passou do prazo de inadimplencia: vermelho
    assert _status_cliente(cliente, _agr(_mov("COMPRA", 50, 120)), 90)[1] == "erro"
    # ate' 2 meses: fiado em aberto normal
    assert _status_cliente(cliente, _agr(_mov("COMPRA", 50, 50)), 90) == ("Fiado em aberto", "info")
