"""Smoke test de FichaClienteDialog._montar_html_extrato -- confere
que o extrato continua usando o template premium compartilhado (ver
utils/documento_html.py, Fase 6 Onda 5) depois da extracao do
cabecalho/tabela/total que antes eram uma copia local."""
from unittest import mock

from telas.ficha_cliente import FichaClienteDialog

CLIENTE = {
    "id": 1,
    "nome": "Marcos Silva",
    "cpf_cnpj": "123.456.789-00",
    "telefone": "11988887777",
}

MOVIMENTOS = [
    (
        {
            "data": "2026-09-10T10:00:00",
            "tipo": "COMPRA",
            "valor": 150.0,
            "descricao": "Compra avulsa",
            "venda_id": None,
        },
        150.0,
    ),
]


def _instancia_minima():
    """Contorna o __init__ pesado (carrega dados via rede) -- só seta
    os atributos que _montar_html_extrato de fato lê."""

    dialogo = FichaClienteDialog.__new__(FichaClienteDialog)
    dialogo.cliente = CLIENTE
    dialogo._movimentos = MOVIMENTOS
    return dialogo


def test_montar_html_extrato_usa_template_premium_compartilhado():

    dialogo = _instancia_minima()

    with mock.patch(
        "telas.ficha_cliente.extrato.api.configuracoes",
        return_value={"nome_loja": "Loja Teste", "telefone": "11999998888"},
    ), mock.patch(
        "telas.ficha_cliente.extrato.api.me", return_value={"nome": "Ana Vendedora"}
    ), mock.patch(
        "telas.ficha_cliente.extrato.saldo_cliente", return_value=150.0
    ), mock.patch(
        "telas.ficha_cliente.extrato.listar_observacoes_cliente", return_value=[]
    ):
        html = dialogo._montar_html_extrato()

    assert "EXTRATO FINANCEIRO" in html
    assert "Loja Teste" in html
    assert "Marcos Silva" in html
    assert "Compra avulsa" in html
    assert "TOTAL DEVEDOR" in html
    assert "R$ 150,00" in html
    assert "px;'" not in html and 'px"' not in html
