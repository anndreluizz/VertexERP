from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.caixa import Caixa
from app.models.cliente import Cliente
from app.models.compra import Compra
from app.models.conta_pagar import ContaPagar
from app.models.conta_receber import ContaReceber
from app.models.fornecedor import Fornecedor
from app.models.produto import Produto
from app.models.venda import Venda

from app.enums.status_conta_receber import StatusContaReceber
from app.enums.status_conta_pagar import StatusContaPagar


class DashboardService:

    @staticmethod
    def resumo(db: Session):

        hoje = date.today()

        vendas_hoje = (
            db.query(func.coalesce(func.sum(Venda.valor_total), 0))
            .filter(func.date(Venda.data) == hoje)
            .scalar()
        )

        vendas_hoje_qtd = (
            db.query(Venda)
            .filter(func.date(Venda.data) == hoje)
            .count()
        )

        vendas_mes = (
            db.query(func.coalesce(func.sum(Venda.valor_total), 0))
            .filter(
                func.extract("year", Venda.data) == hoje.year,
                func.extract("month", Venda.data) == hoje.month,
            )
            .scalar()
        )

        compras_hoje = (
            db.query(func.coalesce(func.sum(Compra.valor_total), 0))
            .filter(func.date(Compra.data) == hoje)
            .scalar()
        )

        saldo_caixa = (
            db.query(Caixa.saldo_final)
            .filter(Caixa.status == "ABERTO")
            .scalar()
        ) or 0

        contas_receber = (
            db.query(func.coalesce(func.sum(ContaReceber.valor), 0))
            .filter(
                ContaReceber.status ==
                StatusContaReceber.PENDENTE.value
            )
            .scalar()
        )

        contas_pagar = (
            db.query(func.coalesce(func.sum(ContaPagar.valor), 0))
            .filter(
                ContaPagar.status ==
                StatusContaPagar.PENDENTE.value
            )
            .scalar()
        )

        clientes = db.query(Cliente).count()

        fornecedores = db.query(Fornecedor).count()

        produtos = db.query(Produto).count()

        estoque_baixo = (
            db.query(Produto)
            .filter(
                Produto.estoque <= Produto.estoque_minimo
            )
            .count()
        )

        return {
            "vendas_hoje": float(vendas_hoje),
            "vendas_hoje_qtd": vendas_hoje_qtd,
            "vendas_mes": float(vendas_mes),
            "compras_hoje": float(compras_hoje),
            "saldo_caixa": float(saldo_caixa),
            "contas_receber": float(contas_receber),
            "contas_pagar": float(contas_pagar),
            "clientes": clientes,
            "fornecedores": fornecedores,
            "produtos": produtos,
            "estoque_baixo": estoque_baixo,
        }