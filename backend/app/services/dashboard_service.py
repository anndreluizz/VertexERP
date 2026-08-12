from datetime import datetime, timedelta

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
from app.repositories.movimento_fiado_repository import (
    MovimentoFiadoRepository,
)


class DashboardService:

    @staticmethod
    def resumo(db: Session):

        # Venda.data/Compra.data são gravados com datetime.utcnow(), então
        # "hoje" também precisa ser a data em UTC — usar a data local aqui
        # causa mismatch perto da virada da meia-noite UTC.
        hoje = datetime.utcnow().date()

        # Só conta vendas de fato finalizadas -- comandas de mesa ainda
        # ABERTAS não são receita. Usa data_fechamento quando existir
        # (fechamento de mesa), senão cai para "data" (venda de balcão).
        vendas_hoje = (
            db.query(func.coalesce(func.sum(Venda.valor_total), 0))
            .filter(Venda.status == "FINALIZADA")
            .filter(
                func.date(
                    func.coalesce(Venda.data_fechamento, Venda.data)
                ) == hoje
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

        clientes = (
            db.query(Cliente)
            .filter(Cliente.ativo.is_(True))
            .count()
        )

        fornecedores = db.query(Fornecedor).count()

        produtos = db.query(Produto).count()

        estoque_baixo = (
            db.query(Produto)
            .filter(
                Produto.estoque <= Produto.estoque_minimo
            )
            .count()
        )

        total_fiado_devedor = MovimentoFiadoRepository.total_devedor(db)

        vendas_ontem = (
            db.query(func.coalesce(func.sum(Venda.valor_total), 0))
            .filter(Venda.status == "FINALIZADA")
            .filter(
                func.date(
                    func.coalesce(Venda.data_fechamento, Venda.data)
                ) == hoje - timedelta(days=1)
            )
            .scalar()
        )

        vendas_ultimos_7_dias = DashboardService._vendas_ultimos_7_dias(
            db, hoje
        )

        return {
            "vendas_hoje": float(vendas_hoje),
            "vendas_ontem": float(vendas_ontem),
            "compras_hoje": float(compras_hoje),
            "saldo_caixa": float(saldo_caixa),
            "contas_receber": float(contas_receber),
            "contas_pagar": float(contas_pagar),
            "total_fiado_devedor": float(total_fiado_devedor),
            "clientes": clientes,
            "fornecedores": fornecedores,
            "produtos": produtos,
            "estoque_baixo": estoque_baixo,
            "vendas_ultimos_7_dias": vendas_ultimos_7_dias,
        }

    @staticmethod
    def _vendas_ultimos_7_dias(db: Session, hoje):
        """Total de vendas finalizadas por dia, dos últimos 7 dias
        (incluindo hoje) — alimenta o gráfico do dashboard."""

        dia_coluna = func.date(
            func.coalesce(Venda.data_fechamento, Venda.data)
        )

        resultados = (
            db.query(dia_coluna.label("dia"), func.sum(Venda.valor_total))
            .filter(Venda.status == "FINALIZADA")
            .filter(dia_coluna >= hoje - timedelta(days=6))
            .group_by("dia")
            .all()
        )

        totais_por_dia = {str(dia): float(total) for dia, total in resultados}

        return [
            {
                "data": (hoje - timedelta(days=i)).isoformat(),
                "total": totais_por_dia.get(
                    (hoje - timedelta(days=i)).isoformat(), 0.0
                ),
            }
            for i in range(6, -1, -1)
        ]