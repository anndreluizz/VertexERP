"""Formatação de valores pro padrão brasileiro na interface -- em
nenhum lugar da tela um valor em dinheiro deveria aparecer como
"R$ 2220.00" (ponto), sempre "R$ 2.220,00" (milhar com ponto, decimal
com vírgula)."""


def formatar_moeda(valor, com_simbolo=True):
    """1234.5 -> "R$ 1.234,50" (ou "1.234,50" com com_simbolo=False)."""

    texto = f"{float(valor or 0):,.2f}"

    # o :,.2f do Python usa o padrao americano (1,234.50) -- troca pro
    # brasileiro trocando os separadores via um marcador temporario,
    # pra nao vira "1.234.50" trocando os dois de uma vez só
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")

    return f"R$ {texto}" if com_simbolo else texto


# nome legivel das formas de pagamento (enum do backend) -- telas e recibos
NOMES_FORMA = {
    "DINHEIRO": "Dinheiro",
    "PIX": "Pix",
    "DEBITO": "Débito",
    "CREDITO": "Crédito",
    "BOLETO": "Boleto",
    "PRAZO": "Fiado",
    "CARTAO": "Cartão",
    "TRANSFERENCIA": "Transferência",
    "CHEQUE": "Cheque",
}


def linhas_resumo_caixa(resumo):
    """Linhas do resumo de um turno, na mesma ordem da tela de Caixa:
    o que fica na gaveta e o que entrou fora dela (PIX/cartão), com o
    fiado recebido separado por forma. Usado no extrato e no cupom do
    fechamento e em Caixas anteriores. Linhas que só existem em caixa
    antigo (boleto saindo da gaveta) ou forma rara somem quando zeradas.
    Devolve [(rótulo, valor)]."""

    def v(chave):
        return float(resumo.get(chave, 0) or 0)

    linhas = [
        ("Troco inicial", v("saldo_inicial")),
        ("Vendas em dinheiro", v("vendas_dinheiro")),
        ("Fiado recebido em dinheiro", v("recebimentos_fiado_dinheiro")),
        ("Suprimentos", v("suprimentos")),
        ("Sangrias", -v("sangrias")),
        ("Contas pagas (boleto)", -v("contas_pagas_caixa")),
        ("Vendas PIX", v("vendas_pix")),
        ("Fiado recebido no PIX", v("recebimentos_fiado_pix")),
        ("Vendas cartão", v("vendas_cartao")),
        ("Fiado recebido no cartão", v("recebimentos_fiado_cartao")),
        ("Fiado recebido (outras formas)", v("recebimentos_fiado_outros")),
    ]
    opcionais = {"Contas pagas (boleto)", "Fiado recebido (outras formas)"}
    return [(r, x) for r, x in linhas if r not in opcionais or abs(x) >= 0.01]


def nome_forma(codigo):
    return NOMES_FORMA.get(codigo, codigo)
