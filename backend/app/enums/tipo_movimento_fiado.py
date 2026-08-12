from enum import Enum


class TipoMovimentoFiado(str, Enum):
    COMPRA = "COMPRA"
    PAGAMENTO = "PAGAMENTO"
