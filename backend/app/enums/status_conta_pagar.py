from enum import Enum


class StatusContaPagar(str, Enum):
    PENDENTE = "PENDENTE"
    PAGO = "PAGO"
    CANCELADO = "CANCELADO"