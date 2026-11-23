"""Contas a Pagar: so' as mais urgentes viram widget e a busca reaproveita
as linhas ja' montadas (300 contas levavam ~2 s a cada letra)."""
from datetime import date, timedelta
from unittest import mock

from telas import contas_pagar as tela
from telas.contas_pagar import MAX_LINHAS, ContasPagar


def _contas(n):
    hoje = date.today()
    return [{
        "id": i, "descricao": f"BOLETO {i}", "categoria": "Aluguel", "valor": 100 + i,
        "status": "PENDENTE", "data_vencimento": (hoje + timedelta(days=i % 40 - 20)).isoformat(),
    } for i in range(n)]


def _tela(monkeypatch):
    monkeypatch.setattr(tela, "rodar_em_thread", lambda *a, **k: None)
    with mock.patch("services.preferencias_service.carregar", return_value={}):
        return ContasPagar()


def test_so_monta_as_primeiras_e_avisa(_qapp, monkeypatch):
    w = _tela(monkeypatch)
    w._ao_carregar_sucesso(_contas(150))
    assert len(w._linhas) == MAX_LINHAS


def test_busca_reaproveita_as_linhas(_qapp, monkeypatch):
    w = _tela(monkeypatch)
    w._ao_carregar_sucesso(_contas(60))
    montadas = []
    original = tela.DespesaLinha
    monkeypatch.setattr(tela, "DespesaLinha", lambda *a: montadas.append(1) or original(*a))

    for letra in "boleto 1":
        w.pesquisa.insert(letra)
    w.pesquisa.clear()
    assert montadas == []
    assert len(w._linhas) == 60
