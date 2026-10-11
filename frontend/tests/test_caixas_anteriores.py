"""Tela Caixas anteriores: lista os caixas fechados e separa vendas de
recebimentos do turno escolhido."""
from telas import caixas_anteriores as tela

CAIXA = {
    "id": 7, "status": "FECHADO", "data_abertura": "2026-10-09T08:00:00",
    "data_fechamento": "2026-10-09T18:05:00", "saldo_final": "485.00",
    "valor_contado": None, "observacoes": None, "usuario_nome": "ANDRE",
}
MOVIMENTOS = [
    {"tipo": "VENDA", "descricao": "Venda #30", "valor": 50.0, "forma_pagamento": "DINHEIRO", "data": "2026-10-09T09:39:00"},
    {"tipo": "RECEBIMENTO_FIADO", "descricao": "JOSE AZEVEDO", "valor": 150.0, "forma_pagamento": "PIX", "data": "2026-10-09T16:30:00"},
    {"tipo": "SANGRIA", "descricao": "Funcionaria", "valor": 30.0, "forma_pagamento": None, "data": "2026-10-09T12:00:00"},
]


def test_separa_vendas_de_recebimentos():
    vendas, outros = tela.separar_movimentos(MOVIMENTOS)
    assert [m["tipo"] for m in vendas] == ["VENDA"]
    assert {m["tipo"] for m in outros} == {"RECEBIMENTO_FIADO", "SANGRIA"}


def test_mostra_caixa_escolhido(_qapp, monkeypatch):
    dialogo = tela.CaixasAnterioresDialog.__new__(tela.CaixasAnterioresDialog)
    monkeypatch.setattr(tela, "rodar_em_thread", lambda *a, **k: None)
    tela.CaixasAnterioresDialog.__init__(dialogo)

    dialogo._ao_carregar_caixas([CAIXA, {**CAIXA, "id": 8, "status": "ABERTO"}])
    assert dialogo.tabela_caixas.rowCount() == 1  # so os fechados

    dialogo.caixa_atual = CAIXA
    dialogo._ao_carregar_detalhe((7, {"total_previsto": 485, "recebimentos_fiado": 150}, MOVIMENTOS))
    assert dialogo.tabela_vendas.rowCount() == 1
    assert dialogo.tabela_recebimentos.rowCount() == 2
    assert "R$ 150,00" in dialogo.lbl_recebimentos.text()
    assert "não contado" in dialogo.lbl_resumo.text()
    assert dialogo.bt_imprimir.isEnabled()


def test_abre_ja_com_o_caixa_escolhido(_qapp, monkeypatch):
    dialogo = tela.CaixasAnterioresDialog.__new__(tela.CaixasAnterioresDialog)
    monkeypatch.setattr(tela, "rodar_em_thread", lambda *a, **k: None)
    tela.CaixasAnterioresDialog.__init__(dialogo, caixa_id=8)

    dialogo._ao_carregar_caixas([CAIXA, {**CAIXA, "id": 8}])
    assert dialogo.tabela_caixas.currentRow() == 1
    assert dialogo.caixa_atual["id"] == 8


def test_relatorios_duplo_clique_abre_caixa_fechado():
    from unittest import mock
    from telas.relatorios import Relatorios

    rel = Relatorios.__new__(Relatorios)
    rel.caixas = [{**CAIXA, "id": 9, "status": "ABERTO"}, CAIXA]
    with mock.patch.object(Relatorios, "abrir_caixas_anteriores") as abrir:
        rel._ao_duplo_clique_caixa(0, 0)  # aberto: nao tem fechamento
        abrir.assert_not_called()
        rel._ao_duplo_clique_caixa(1, 3)
        abrir.assert_called_once_with(7)
