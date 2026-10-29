"""PDF de caixas (Relatórios > Caixa): cada venda cai no caixa certo,
com os itens, e cancelada não soma."""
from telas.relatorios import pdf_caixas

CAIXA = {
    "id": 7, "status": "FECHADO", "usuario_id": 1, "usuario_nome": "ANDRE",
    "data_abertura": "2026-10-09T08:00:00", "data_fechamento": "2026-10-09T18:05:00",
    "valor_contado": "100.00", "observacoes": "tudo certo",
}
ITEM = {"produto_id": 3, "produto_nome": "BLUSA", "quantidade": 2, "valor_unitario": "10.00", "subtotal": "20.00"}
VENDAS = [
    {"id": 30, "usuario_id": 1, "data": "2026-10-09T09:39:00", "valor_total": "20.00", "desconto": "0",
     "status": "CONCLUIDA", "forma_pagamento": "PIX", "cliente_nome": "MARIA", "itens": [ITEM]},
    {"id": 31, "usuario_id": 1, "data": "2026-10-09T10:00:00", "valor_total": "99.00", "desconto": "0",
     "status": "CANCELADA", "forma_pagamento": "DINHEIRO", "itens": [ITEM]},
    {"id": 32, "usuario_id": 2, "data": "2026-10-09T10:00:00", "valor_total": "5.00", "desconto": "0",
     "status": "CONCLUIDA", "forma_pagamento": "DINHEIRO", "itens": []},  # outro operador
    {"id": 33, "usuario_id": 1, "data": "2026-10-09T19:00:00", "valor_total": "5.00", "desconto": "0",
     "status": "CONCLUIDA", "forma_pagamento": "DINHEIRO", "itens": []},  # depois de fechar
]
MOVS = [{"tipo": "RECEBIMENTO_FIADO", "descricao": "JOSE", "valor": 50, "forma_pagamento": "DINHEIRO",
         "data": "2026-10-09T16:30:00"}]


def test_vendas_do_caixa():
    assert [v["id"] for v in pdf_caixas.vendas_do_caixa(CAIXA, VENDAS)] == [30, 31]


def test_monta_html():
    dados = {"detalhes": [(CAIXA, {"total_previsto": 100, "saldo_inicial": 50}, MOVS)],
             "vendas": VENDAS, "entradas": {"total": 70}}
    html = pdf_caixas.montar_html(dados, "3.L.A", "Outubro/2026")
    assert "2x BLUSA" in html and "MARIA" in html and "JOSE" in html
    assert "Vendas (1) · R$ 20,00" in html  # cancelada fora do total
    assert "<s>R$ 99,00</s>" in html
    assert "confere" in html and "tudo certo" in html


def test_negativo_com_sinal_na_frente():
    assert pdf_caixas._moeda(-30) == "- R$ 30,00"
