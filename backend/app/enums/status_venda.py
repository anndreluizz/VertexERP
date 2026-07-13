from enum import Enum


class StatusVenda(str, Enum):
    ABERTA = "ABERTA"
    FINALIZADA = "FINALIZADA"
    CANCELADA = "CANCELADA"