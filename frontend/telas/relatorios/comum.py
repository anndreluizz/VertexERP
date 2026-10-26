from services.produto_service import listar_produtos
from services.caixa_service import historico_caixa
from services.loja_service import listar_lojas
from services.worker import em_paralelo
from design.widgets import cor_forma_pagamento


def _listar_lojas_para_combo(combo):
    """Roda na worker thread -- `combo` so' viaja de ida e volta junto
    com o resultado (nao chamado/tocado aqui, so' repassado; ver
    services/worker.py sobre por que o callback nao pode ser uma
    lambda que "lembra" o combo via closure)."""
    return listar_lojas(), combo


def _buscar_dados_relatorio_geral(loja_id_caixa):
    """Roda na worker thread -- as 2 chamadas que carregar() precisa
    (a 3a, relatorio_vendas, fica em _atualizar_financeiro, que ja e'
    independente/refeita sozinha quando o filtro financeiro muda).
    As 2 sao independentes, entao disparam em paralelo."""
    return em_paralelo((listar_produtos,), (historico_caixa, loja_id_caixa))


NOMES_FORMA_PAGAMENTO = {
    "DINHEIRO": "Dinheiro",
    "PIX": "PIX",
    "DEBITO": "Débito",
    "CREDITO": "Crédito",
    "BOLETO": "Boleto",
    "PRAZO": "Crediário",
    "CARTAO": "Cartão",
    "TRANSFERENCIA": "Transferência",
}


class _CoresFormaPagamento:
    """Mesmas cores do PDV/fiado/despesa (cor_forma_pagamento) -- antes
    era um dict fixo aqui com outra paleta (Débito laranja, PIX azul) e
    calculado no import, antes do tema escuro existir. Mantém o .get()
    porque telas/dashboard.py usa CORES_FORMA_PAGAMENTO.get(forma, cor)."""

    def get(self, forma, _padrao=None):
        return cor_forma_pagamento(forma)

    def __getitem__(self, forma):
        return cor_forma_pagamento(forma)


CORES_FORMA_PAGAMENTO = _CoresFormaPagamento()
