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
