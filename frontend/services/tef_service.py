"""Estrutura preparada pra uma integração futura de TEF/POS (Transferência
Eletrônica de Fundos) — pagamento por débito/crédito processado direto por
uma maquininha, sem digitar o valor duas vezes.

Nenhuma maquininha foi integrada ainda (não há SDK/parceiro escolhido — ver
o item "Integrações (TEF/POS)" em Configurações, marcado como "em breve").
Esta classe documenta o contrato que uma implementação real vai precisar
seguir, pra o dia que essa integração acontecer não exigir redesenhar o
fluxo de pagamento inteiro — só trocar esta classe por uma implementação
de verdade."""


class TefService:

    def disponivel(self):
        """Se True, o PDV pode oferecer TEF como opção de pagamento.
        Sempre False até uma implementação real existir."""
        return False

    def iniciar_pagamento(self, valor, forma_pagamento):
        """Enviaria o valor pra maquininha e aguardaria a confirmação
        (aprovado/negado) + os dados da transação (NSU, autorização,
        bandeira) que hoje o comprovante não tem porque não existem."""
        raise NotImplementedError(
            "TEF ainda não está integrado. Use Débito/Crédito manual."
        )

    def cancelar_pagamento(self, transacao_id):
        """Enviaria um cancelamento/estorno pra maquininha, referente a
        uma transação TEF específica."""
        raise NotImplementedError(
            "TEF ainda não está integrado."
        )
