"""Lista de movimentos do caixa: venda no fiado nao parece dinheiro
entrando, e o estorno aparece ligado a' venda (caso real de 20/10)."""
from telas import caixa
from telas.caixa import _descricao_movimento, _tipo_exibido

MOVIMENTOS = [
    {"tipo": "VENDA", "forma_pagamento": "DINHEIRO", "valor": 36.0, "descricao": "Venda #151", "data": "2026-10-20T16:57:00"},
    {"tipo": "VENDA", "forma_pagamento": "PRAZO", "valor": 147.99, "descricao": "Venda #148", "data": "2026-10-20T15:50:00"},
    {"tipo": "ESTORNO", "forma_pagamento": "DINHEIRO", "valor": -150.0, "descricao": "Estorno da venda #146", "data": "2026-10-20T15:49:00"},
    {"tipo": "ESTORNO", "forma_pagamento": "PRAZO", "valor": -84.99, "descricao": "Estorno da venda #146", "data": "2026-10-20T15:49:00"},
]


def test_fiado_tem_tipo_proprio_e_aviso():
    assert _tipo_exibido(MOVIMENTOS[0]) == "VENDA"
    assert _tipo_exibido(MOVIMENTOS[1]) == "VENDA_FIADO"
    assert _descricao_movimento(MOVIMENTOS[1], "VENDA_FIADO") == "Venda #148 · não mexe no dinheiro do caixa"


def test_estorno_vira_venda_cancelada():
    assert _descricao_movimento(MOVIMENTOS[2], "ESTORNO") == "Venda #146 cancelada"
    assert _tipo_exibido(MOVIMENTOS[3]) == "ESTORNO_FIADO"


def test_fiado_recebido_em_dinheiro_entra_no_caixa():
    mov = {"tipo": "RECEBIMENTO_FIADO", "forma_pagamento": "DINHEIRO", "descricao": "Pagamento fiado - ANA"}
    assert _descricao_movimento(mov, _tipo_exibido(mov)) == "Pagamento fiado - ANA"


def test_tabela_mostra_a_forma():
    # so' a lista: a tela inteira busca dados no servidor ao abrir
    from types import SimpleNamespace
    from PySide6.QtWidgets import QLabel, QTableWidget

    tela = SimpleNamespace(tabela_movimentos=QTableWidget(0, 5), lbl_sem_movimentos=QLabel())
    caixa.Caixa.carregar_movimentos(tela, MOVIMENTOS)
    formas = [tela.tabela_movimentos.item(i, 2).text() for i in range(4)]
    assert formas == ["Dinheiro", "Fiado", "Dinheiro", "Fiado"]

    # recarregar (botao Atualizar) nao deixa o widget antigo por baixo
    caixa.Caixa.carregar_movimentos(tela, MOVIMENTOS[:1])
    assert tela.tabela_movimentos.rowCount() == 1
    assert tela.tabela_movimentos.cellWidget(0, 3) is not None
