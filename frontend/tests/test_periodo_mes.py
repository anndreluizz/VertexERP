"""Filtro por mes fechado ("Agosto/2026") nos combos de periodo."""
from datetime import date

from telas.inteligencia_negocios import datas_do_periodo
from utils.periodo import intervalo_mes, meses_anteriores, meses_recentes, meses_seguintes

HOJE = date(2026, 1, 20)


def test_listas_viram_o_ano():
    assert meses_recentes(HOJE, 4) == ["Janeiro/2026", "Dezembro/2025", "Novembro/2025", "Outubro/2025"]
    assert meses_anteriores(HOJE, 2) == ["Novembro/2025", "Outubro/2025"]  # pula o "Mes anterior"
    assert meses_seguintes(date(2026, 11, 5), 3) == ["Dezembro/2026", "Janeiro/2027", "Fevereiro/2027"]


def test_intervalo_do_mes():
    assert intervalo_mes("Fevereiro/2028") == (date(2028, 2, 1), date(2028, 2, 29))  # bissexto
    assert intervalo_mes("Dezembro/2025") == (date(2025, 12, 1), date(2025, 12, 31))
    assert intervalo_mes("Este mês") is None
    assert intervalo_mes("Período personalizado") is None


def test_bi_aceita_mes():
    assert datas_do_periodo("Agosto/2026", HOJE) == (date(2026, 8, 1), date(2026, 8, 31))
    assert datas_do_periodo("Período personalizado", HOJE) is None


def test_contas_a_pagar_filtra_pelo_mes_do_vencimento():
    from types import SimpleNamespace
    from telas.contas_pagar import ContasPagar

    tela = SimpleNamespace(filtro_periodo="Novembro/2026")
    dentro = ContasPagar._dentro_do_periodo
    assert dentro(tela, {"data_vencimento": "2026-11-30"})
    assert not dentro(tela, {"data_vencimento": "2026-12-01"})


class _Card:
    def __init__(self):
        self.titulo = self.valor = self.legenda = None

    def definir_titulo(self, t):
        self.titulo = t

    def definir_valor(self, v):
        self.valor = v

    def definir_legenda(self, l):
        self.legenda = l


def test_cards_de_contas_a_pagar_seguem_o_mes_escolhido():
    from types import SimpleNamespace
    from telas.contas_pagar import ContasPagar

    proximo = meses_seguintes(quantos=1)[0]  # ex.: "Novembro/2026"
    inicio, fim = intervalo_mes(proximo)
    cards = [_Card() for _ in range(4)]
    tela = SimpleNamespace(filtro_periodo=proximo, _cards_kpi=cards, card_aberto=cards[0],
                           card_vencidas=cards[1], card_proximos_7=cards[2], card_pago=cards[3])
    contas = [
        {"status": "PENDENTE", "valor": 100, "data_vencimento": inicio.isoformat()},
        {"status": "PAGO", "valor": 40, "data_vencimento": inicio.isoformat(), "data_pagamento": fim.isoformat()},
        {"status": "PENDENTE", "valor": 999, "data_vencimento": "2020-01-01"},  # outro mes
    ]
    pago_em = lambda c: date.fromisoformat(c["data_pagamento"]) if c.get("data_pagamento") else None
    ContasPagar._cards_do_mes(tela, contas, pago_em)

    nome = proximo.split("/")[0].lower()
    assert [c.titulo for c in cards] == [f"Vence em {nome}", f"Atrasadas em {nome}", f"Falta pagar em {nome}", f"Pago em {nome}"]
    assert [c.valor for c in cards] == ["R$ 140,00", "R$ 0,00", "R$ 100,00", "R$ 40,00"]

    tela.filtro_periodo = "TODOS"  # sem mes: titulos de sempre
    ContasPagar._cards_do_mes(tela, contas, pago_em)
    assert cards[2].titulo == "Próximos 7 dias"
