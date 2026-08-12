from enum import Enum


class TipoMovimentoEstoque(str, Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
