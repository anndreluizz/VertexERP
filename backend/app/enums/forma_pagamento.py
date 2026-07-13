from enum import Enum


class FormaPagamento(str, Enum):
    DINHEIRO = "DINHEIRO"
    PIX = "PIX"
    DEBITO = "DEBITO"
    CREDITO = "CREDITO"
    BOLETO = "BOLETO"
    PRAZO = "PRAZO"