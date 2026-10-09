from design import tokens
from design.widgets import BotaoSucesso
from telas.sangria import MovimentoGavetaDialog


class SuprimentoWindow(MovimentoGavetaDialog):

    TIPO = "SUPRIMENTO"

    def __init__(self):
        super().__init__(
            "Suprimento", "Reforço de dinheiro na gaveta",
            "arrow-up", tokens.SECUNDARIA_HOVER, tokens.SUCESSO_CLARO,
            "Motivo do suprimento", BotaoSucesso("Confirmar Suprimento", icone_nome="check"),
        )
