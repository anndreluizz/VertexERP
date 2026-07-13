from enum import Enum


class StatusContaReceber(str, Enum):
    PENDENTE = "PENDENTE"
    RECEBIDO = "RECEBIDO"
    CANCELADO = "CANCELADO"