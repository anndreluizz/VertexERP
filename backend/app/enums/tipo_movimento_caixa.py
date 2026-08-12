from enum import Enum


class TipoMovimentoCaixa(str, Enum):
    VENDA = "VENDA"
    SUPRIMENTO = "SUPRIMENTO"
    SANGRIA = "SANGRIA"
    RECEBIMENTO = "RECEBIMENTO"
    PAGAMENTO = "PAGAMENTO"
    AJUSTE = "AJUSTE"
    ESTORNO = "ESTORNO"