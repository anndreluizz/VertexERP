from design import tokens
from design.widgets import BotaoSucesso
from telas.sangria import MovimentoGavetaDialog


class SuprimentoWindow(MovimentoGavetaDialog):

    TIPO = "SUPRIMENTO"
    SINAL = 1

    def __init__(self, esperado=None):
        super().__init__(
            "Suprimento", "Reforço de dinheiro na gaveta",
            "arrow-up", tokens.SECUNDARIA_HOVER, tokens.SUCESSO_CLARO,
            "Motivo do suprimento", BotaoSucesso("Confirmar Suprimento", icone_nome="check"),
            tokens.SECUNDARIA_ESCURA,
            [20, 50, 100, 200, 300],
            ["Troco extra", "Reforço de caixa", "Devolução do cofre"],
            esperado,
        )
