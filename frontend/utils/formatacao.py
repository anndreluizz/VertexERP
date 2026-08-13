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
