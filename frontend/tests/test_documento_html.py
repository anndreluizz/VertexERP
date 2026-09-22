"""Smoke test do template compartilhado de documento impresso (ver
utils/documento_html.py, Fase 6 Onda 5) -- confere que o comprovante
de venda continua renderizando os mesmos elementos-chave depois de
extrair cabecalho/tabela/total pro modulo compartilhado."""
from services.comprovante_service import gerar_html_comprovante
from utils.documento_html import cabecalho_tabela, linha_zebra, bloco_total


DADOS_VENDA = {
    "venda_id": 42,
    "data": "2026-09-21T14:30:00",
    "usuario_nome": "Ana Vendedora",
    "cliente_nome": "João Cliente",
    "cliente_cpf_cnpj": "123.456.789-00",
    "itens": [
        {
            "produto_id": 1,
            "nome": "Camiseta Azul",
            "quantidade": 2,
            "valor_unitario": 49.9,
            "subtotal": 99.8,
        },
    ],
    "desconto": 0,
    "valor_total": 99.8,
    "forma_pagamento": "PIX",
    "forma_pagamento_2": None,
    "valor_forma_2": None,
    "observacao": None,
    "situacao": "PAGO",
    "saldo_devedor_cliente": None,
}

CONFIG_LOJA = {
    "nome_loja": "Loja Teste",
    "endereco": "Rua das Flores, 123",
    "telefone": "11999998888",
    "cnpj_cpf": "00.000.000/0001-00",
}


def test_gerar_html_comprovante_traz_cabecalho_itens_e_total():

    html = gerar_html_comprovante(DADOS_VENDA, CONFIG_LOJA, logo_bytes=None)

    assert "Loja Teste" in html
    assert "COMPROVANTE DE VENDA" in html
    assert "Pedido nº: 42" in html
    assert "Camiseta Azul" in html
    assert "João Cliente" in html
    assert "R$ 99,80" in html
    # sem pixel em font-size (ver docstring de gerar_html_comprovante
    # sobre por que isso quebra a impressao no QPrinter)
    assert "px;'" not in html and 'px"' not in html


def test_cabecalho_tabela_respeita_alinhamentos():

    html = cabecalho_tabela(["A", "B"], ["left", "right"])

    assert "text-align:left" in html
    assert "text-align:right" in html
    assert "<th" in html


def test_linha_zebra_alterna_cor_por_indice():

    par = linha_zebra(["x"], 0)
    impar = linha_zebra(["x"], 1)

    assert "#FFFFFF" in par
    assert "#F8FAFC" in impar


def test_bloco_total_formata_rotulo_e_valor():

    html = bloco_total("TOTAL", "R$ 10,00")

    assert "TOTAL" in html
    assert "R$ 10,00" in html
