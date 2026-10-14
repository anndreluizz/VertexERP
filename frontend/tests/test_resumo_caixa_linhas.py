from utils.formatacao import linhas_resumo_caixa


def test_linhas_do_caixa_de_10_10_fecham_com_a_gaveta():
    # caixa real de 10/10: boletos Marlan + Natura (1.610,24) sairam da
    # gaveta e a loja lancou suprimento pra compensar
    resumo = {
        "saldo_inicial": 4, "vendas_dinheiro": 155, "recebimentos_fiado_dinheiro": 239,
        "suprimentos": 1656.24, "sangrias": 15, "contas_pagas_caixa": 1610.24,
        "vendas_pix": 0, "recebimentos_fiado_pix": 50,
        "vendas_cartao": 0, "recebimentos_fiado_cartao": 300,
        "recebimentos_fiado_outros": 0, "total_previsto": 429, "total_geral": 779,
    }
    linhas = dict(linhas_resumo_caixa(resumo))

    gaveta = sum(v for r, v in linhas.items() if r not in (
        "Vendas PIX", "Fiado recebido no PIX", "Vendas cartão", "Fiado recebido no cartão",
    ))
    assert round(gaveta, 2) == 429
    assert round(sum(linhas.values()), 2) == 779
    assert linhas["Contas pagas (boleto)"] == -1610.24
    assert "Fiado recebido (outras formas)" not in linhas


def test_caixa_novo_nao_mostra_linha_de_boleto():
    linhas = dict(linhas_resumo_caixa({"saldo_inicial": 10}))
    assert "Contas pagas (boleto)" not in linhas
    assert linhas["Fiado recebido no PIX"] == 0
