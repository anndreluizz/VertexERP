from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.caixa import Caixa
from app.repositories.conta_pagar_repository import ContaPagarRepository
from app.repositories.conta_receber_repository import (
    ContaReceberRepository,
)


class FinanceiroService:

    @staticmethod
    def fluxo_caixa(db: Session, dias: int = 30, loja_id: int | None = None):

        # soma os caixas abertos no momento -- fluxo de caixa e uma
        # visao financeira geral da loja, nao de um operador so (mesmo
        # criterio do KPI 'saldo_caixa' do dashboard, inclusive o
        # filtro por loja_id).
        query_saldo_atual = db.query(
            func.coalesce(func.sum(Caixa.saldo_final), 0)
        ).filter(Caixa.status == "ABERTO")

        if loja_id is not None:
            query_saldo_atual = query_saldo_atual.filter(
                Caixa.loja_id == loja_id
            )

        saldo_atual = query_saldo_atual.scalar() or Decimal("0")

        limite = datetime.now() + timedelta(days=dias)

        receber = [
            conta
            for conta in ContaReceberRepository.listar_pendentes(db, loja_id)
            if conta.data_vencimento <= limite
        ]

        pagar = [
            conta
            for conta in ContaPagarRepository.listar_pendentes(db, loja_id)
            if conta.data_vencimento <= limite
        ]

        total_a_receber = sum(
            (conta.valor for conta in receber), Decimal("0")
        )
        total_a_pagar = sum(
            (conta.valor for conta in pagar), Decimal("0")
        )

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
