"""Ficha do cliente: compra no crediario mostra cada produto com o valor
dele, nao so' o total da venda."""
from telas.ficha_cliente.historico import HistoricoMixin


class _Ficha(HistoricoMixin):
    _nomes_produto = {1: "MALBEC", 2: "HIDRATANTE"}
    _vendas_por_id = {7: {"itens": [
        {"produto_id": 1, "quantidade": 1, "subtotal": "189.99"},
        {"produto_id": 2, "quantidade": 2},  # venda antiga sem subtotal
    ]}}


def test_um_produto_por_linha_com_valor():
    mov = {"tipo": "COMPRA", "venda_id": 7, "descricao": "Venda #7"}
    linhas = _Ficha()._descricao_com_itens(mov).split("\n")
    assert linhas[0].startswith("MALBEC x1 — R$") and linhas[0].endswith("189,99")
    assert linhas[1] == "HIDRATANTE x2"
