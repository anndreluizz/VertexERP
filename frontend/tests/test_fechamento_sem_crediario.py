"""O papel do fechamento mostra so' o que foi a vista: nada de crediario."""

from services import impressora_termica_service
from telas import fechar_caixa

MOVS = [
    {"tipo": "VENDA", "forma_pagamento": "DINHEIRO", "valor": 10, "descricao": "Venda #1", "data": "2026-11-02T09:00:00"},
    {"tipo": "VENDA", "forma_pagamento": "PRAZO", "valor": 99, "descricao": "Venda #2", "data": "2026-11-02T09:10:00"},
]
RESUMO = {"vendas_dinheiro": 10, "vendas_prazo": 99, "total_previsto": 10, "total_geral": 10}


def test_imprimir_fechamento_tira_crediario(monkeypatch):
    enviados = {}

    def fake(caixa, resumo, movimentos, *resto):
        enviados["movs"] = movimentos
        return True, None

    monkeypatch.setattr(fechar_caixa.preferencias_service, "carregar_impressora_termica", lambda: {"ativa": True})
    monkeypatch.setattr(impressora_termica_service, "imprimir_fechamento_caixa", fake)
    fechar_caixa.imprimir_fechamento(None, {}, RESUMO, MOVS, 10, "", "Ana", "2026-11-02T18:00:00", {})
    assert [m["descricao"] for m in enviados["movs"]] == ["Venda #1"]


def test_cupom_e_html_sem_linha_de_prazo():
    cupom = impressora_termica_service.gerar_comandos_fechamento_caixa(
        {}, RESUMO, [], 10, "", "Ana", "2026-11-02T18:00:00", {},
    )
    html = fechar_caixa.montar_html_fechamento({}, RESUMO, [], 10, "", "Ana", "2026-11-02T18:00:00", {})
    assert b"prazo" not in bytes(cupom).lower()
    assert "prazo" not in html.lower()
