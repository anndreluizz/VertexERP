from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.caixa_repository import CaixaRepository
from app.repositories.conta_pagar_repository import ContaPagarRepository
from app.repositories.conta_receber_repository import (
    ContaReceberRepository,
)


class FinanceiroService:

    @staticmethod
    def fluxo_caixa(db: Session, dias: int = 30):

        caixa = CaixaRepository.buscar_aberto(db)
        saldo_atual = caixa.saldo_final if caixa else 0.0

        limite = datetime.utcnow() + timedelta(days=dias)

        receber = [
            conta
            for conta in ContaReceberRepository.listar_pendentes(db)
            if conta.data_vencimento <= limite
        ]

        pagar = [
            conta
            for conta in ContaPagarRepository.listar_pendentes(db)
            if conta.data_vencimento <= limite
        ]

        total_a_receber = sum(conta.valor for conta in receber)
        total_a_pagar = sum(conta.valor for conta in pagar)

        itens = [
            {
                "tipo": "A_RECEBER",
                "data_vencimento": conta.data_vencimento,
                "descricao": conta.observacao,
                "valor": conta.valor,
            }
            for conta in receber
        ] + [
            {
                "tipo": "A_PAGAR",
                "data_vencimento": conta.data_vencimento,
                "descricao": conta.observacao,
                "valor": conta.valor,
            }
            for conta in pagar
        ]

        itens.sort(key=lambda item: item["data_vencimento"])

        return {
            "saldo_atual": saldo_atual,
            "total_a_receber": total_a_receber,
            "total_a_pagar": total_a_pagar,
            "saldo_projetado": saldo_atual + total_a_receber - total_a_pagar,
            "itens": itens,
        }
