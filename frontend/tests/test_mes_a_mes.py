"""Quadro "Mes a mes" (Relatorios): totais da coluna Total e lucro sem custo."""
from telas.relatorios.mes_a_mes import montar_quadro


def _mes(mes, fat, vendas, lucro=0, custo_incompleto=False, sobrou=0):
    return {"mes": mes, "faturamento": fat, "quantidade_vendas": vendas, "ticket_medio": fat / vendas if vendas else 0,
            "lucro": lucro, "custo_incompleto": custo_incompleto, "entrou": fat, "vendido_fiado": 0,
            "fiado_recebido": 0, "contas_pagas": 0, "sangrias": 0, "sobrou": sobrou}


def test_total_soma_e_ticket_medio_do_ano():
    quadro = dict(montar_quadro([_mes(1, 100, 2, lucro=40, sobrou=-10), _mes(2, 300, 2, lucro=60, sobrou=50)]))
    assert quadro["Faturamento"] == ["R$ 100,00", "R$ 300,00", "R$ 400,00"]
    assert quadro["Nº de vendas"] == ["2", "2", "4"]
    assert quadro["Ticket médio"][-1] == "R$ 100,00"  # 400 / 4, nao a media dos tickets
    assert quadro["Lucro bruto"] == ["R$ 40,00", "R$ 60,00", "R$ 100,00"]
    assert quadro["Sobrou"] == ["R$ -10,00", "R$ 50,00", "R$ 40,00"]


def test_lucro_sem_custo_vira_traco():
    quadro = dict(montar_quadro([_mes(1, 100, 1, lucro=100, custo_incompleto=True), _mes(2, 50, 1, lucro=20)]))
    assert quadro["Lucro bruto"] == ["—", "R$ 20,00", "—"]
