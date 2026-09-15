from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.caixa import Caixa
from app.models.cliente import Cliente
from app.models.compra import Compra
from app.models.conta_pagar import ContaPagar
from app.models.fornecedor import Fornecedor
from app.models.movimento_fiado import MovimentoFiado
from app.models.produto import Produto
from app.models.venda import Venda

from app.enums.status_conta_pagar import StatusContaPagar
from app.enums.status_venda import StatusVenda
from app.services.movimento_fiado_service import MovimentoFiadoService

# quantos meses (incluindo o atual) entram nos graficos de serie mensal
# do dashboard financeiro do mobile.
MESES_SERIE = 6


class DashboardService:

    @staticmethod
    def _somar_meses(referencia: date, quantidade: int) -> date:
        """Soma/subtrai meses a uma data que sempre cai no dia 1 -- sem
        risco de estouro de dia (dia 31 + 1 mes etc.), por isso nao
        precisa de nenhuma lib externa de datas."""

        indice_mes_zero = referencia.month - 1 + quantidade
        ano = referencia.year + indice_mes_zero // 12
        mes = indice_mes_zero % 12 + 1
        return date(ano, mes, 1)

    @staticmethod
    def _serie_mensal(db: Session, coluna_data, coluna_valor, filtros):
        """Monta uma serie de MESES_SERIE meses (do mais antigo pro mais
        novo, incluindo o mes atual), somando coluna_valor agrupado por
        ano/mes de coluna_data. Meses sem nenhum registro entram com 0.0
        -- o grafico do app sempre mostra os mesmos MESES_SERIE pontos."""

        hoje = date.today()
        inicio = DashboardService._somar_meses(
            hoje.replace(day=1), -(MESES_SERIE - 1)
        )

        linhas = (
            db.query(
                func.extract("year", coluna_data).label("ano"),
                func.extract("month", coluna_data).label("mes"),
                func.coalesce(func.sum(coluna_valor), 0).label("total"),
            )
            .filter(coluna_data >= inicio, *filtros)
            .group_by("ano", "mes")
            .all()
        )

        por_mes = {
            (int(linha.ano), int(linha.mes)): float(linha.total)
            for linha in linhas
        }

        serie = []
        for indice in range(MESES_SERIE):
            referencia = DashboardService._somar_meses(inicio, indice)
            chave = (referencia.year, referencia.month)
            serie.append({
                "mes": referencia.strftime("%Y-%m"),
                "valor": por_mes.get(chave, 0.0),
            })

        return serie

    @staticmethod
    def resumo(db: Session):

        # UTC, nao date.today() (hora local) -- Venda/ContaPagar gravam
        # a data com datetime.utcnow(), entao "hoje" precisa estar no
        # mesmo fuso ou as vendas somem do painel entre 21h e meia-noite
        # (horario de Brasilia, quando UTC ja virou o dia seguinte).
        hoje = datetime.utcnow().date()

        vendas_hoje = (
            db.query(func.coalesce(func.sum(Venda.valor_total), 0))
            .filter(
                func.date(Venda.data) == hoje,
                Venda.status == StatusVenda.FINALIZADA.value,
            )
            .scalar()
        )

        vendas_hoje_qtd = (
            db.query(Venda)
            .filter(
                func.date(Venda.data) == hoje,
                Venda.status == StatusVenda.FINALIZADA.value,
            )
            .count()
        )

        ontem = hoje - timedelta(days=1)

        vendas_ontem = (
            db.query(func.coalesce(func.sum(Venda.valor_total), 0))
            .filter(
                func.date(Venda.data) == ontem,
                Venda.status == StatusVenda.FINALIZADA.value,
            )
            .scalar()
        )

        # total vendido por dia nos ultimos 7 dias (incluindo hoje),
        # do mais antigo pro mais novo -- pro grafico de tendencia
        # curta do dashboard, complementar a serie_recebimentos_mensal
        # (que e por mes, nao por dia).
        inicio_7_dias = hoje - timedelta(days=6)

        linhas_7_dias = (
            db.query(
                func.date(Venda.data).label("dia"),
                func.coalesce(func.sum(Venda.valor_total), 0).label(
                    "total"
                ),
            )
            .filter(
                func.date(Venda.data) >= inicio_7_dias,
                func.date(Venda.data) <= hoje,
                Venda.status == StatusVenda.FINALIZADA.value,
            )
            .group_by("dia")
            .all()
        )

        totais_por_dia = {
            (
                linha.dia
                if isinstance(linha.dia, date)
                else datetime.strptime(linha.dia, "%Y-%m-%d").date()
            ): float(linha.total)
            for linha in linhas_7_dias
        }

        vendas_ultimos_7_dias = [
            {
                "data": (inicio_7_dias + timedelta(days=i)).isoformat(),
                "total": totais_por_dia.get(
                    inicio_7_dias + timedelta(days=i), 0.0
                ),
            }
            for i in range(7)
        ]

        vendas_mes = (
            db.query(func.coalesce(func.sum(Venda.valor_total), 0))
            .filter(
                func.extract("year", Venda.data) == hoje.year,
                func.extract("month", Venda.data) == hoje.month,
                Venda.status == StatusVenda.FINALIZADA.value,
            )
            .scalar()
        )

        compras_hoje = (
            db.query(func.coalesce(func.sum(Compra.valor_total), 0))
            .filter(func.date(Compra.data) == hoje)
            .scalar()
        )

        # soma o saldo de TODOS os caixas abertos no momento — desde
        # que caixa passou a ser por usuario (nao mais um unico por
        # loja), pode haver varias sessoes abertas ao mesmo tempo
        saldo_caixa = (
            db.query(func.coalesce(func.sum(Caixa.saldo_final), 0))
            .filter(Caixa.status == "ABERTO")
            .scalar()
        )

        # ContaReceber e uma tabela legada que nao e mais alimentada
        # desde que a venda fiado passou a gerar MovimentoFiado direto
        # (ver VendaService) -- o saldo real em aberto vem daqui.
        contas_receber = MovimentoFiadoService.saldo_total(db)

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

        # despesas ja vencidas e ainda pendentes -- o motivo de ser o
        # KPI mais "vermelho" do painel financeiro.
        vencidas = (
            db.query(
                func.count(ContaPagar.id),
                func.coalesce(func.sum(ContaPagar.valor), 0),
            )
            .filter(
                ContaPagar.status == StatusContaPagar.PENDENTE.value,
                func.date(ContaPagar.data_vencimento) < hoje,
            )
            .one()
        )

        # pendentes que vencem exatamente hoje -- o gatilho do aviso
        # "X contas vencendo hoje" no topo do dashboard mobile.
        vencendo_hoje = (
            db.query(
                func.count(ContaPagar.id),
                func.coalesce(func.sum(ContaPagar.valor), 0),
            )
            .filter(
                ContaPagar.status == StatusContaPagar.PENDENTE.value,
                func.date(ContaPagar.data_vencimento) == hoje,
            )
            .one()
        )

        # despesas efetivamente pagas hoje (data_pagamento, nao
        # vencimento) -- confirma o que ja saiu da conta da loja hoje.
        pagas_hoje = (
            db.query(
                func.count(ContaPagar.id),
                func.coalesce(func.sum(ContaPagar.valor), 0),
            )
            .filter(
                ContaPagar.status == StatusContaPagar.PAGO.value,
                func.date(ContaPagar.data_pagamento) == hoje,
            )
            .one()
        )

        # fiado recebido hoje -- movimentos do tipo PAGAMENTO (ver
        # MovimentoFiadoRepository.saldo_total, mesmo criterio de sinal).
        fiado_recebido_hoje = (
            db.query(func.coalesce(func.sum(MovimentoFiado.valor), 0))
            .filter(
                MovimentoFiado.tipo == "PAGAMENTO",
                func.date(MovimentoFiado.data) == hoje,
            )
            .scalar()
        )

        # pago x pendente do mes -- mesmo recorte do mes atual, um lado
        # pelo pagamento, outro pelo vencimento (cada um so existe numa
        # das duas colunas de data).
        contas_mes_pago = (
            db.query(func.coalesce(func.sum(ContaPagar.valor), 0))
            .filter(
                ContaPagar.status == StatusContaPagar.PAGO.value,
                func.extract("year", ContaPagar.data_pagamento) == hoje.year,
                func.extract("month", ContaPagar.data_pagamento) == hoje.month,
            )
            .scalar()
        )

        contas_mes_pendente = (
            db.query(func.coalesce(func.sum(ContaPagar.valor), 0))
            .filter(
                ContaPagar.status == StatusContaPagar.PENDENTE.value,
                func.extract("year", ContaPagar.data_vencimento) == hoje.year,
                func.extract("month", ContaPagar.data_vencimento) == hoje.month,
            )
            .scalar()
        )

        serie_recebimentos_mensal = DashboardService._serie_mensal(
            db,
            Venda.data,
            Venda.valor_total,
            filtros=[Venda.status == StatusVenda.FINALIZADA.value],
        )

        serie_pagamentos_mensal = DashboardService._serie_mensal(
            db,
            ContaPagar.data_pagamento,
            ContaPagar.valor,
            filtros=[ContaPagar.status == StatusContaPagar.PAGO.value],
        )

        return {
            "vendas_hoje": float(vendas_hoje),
            "vendas_hoje_qtd": vendas_hoje_qtd,
            "vendas_ontem": float(vendas_ontem),
            "vendas_ultimos_7_dias": vendas_ultimos_7_dias,
            "vendas_mes": float(vendas_mes),
            "compras_hoje": float(compras_hoje),
            "saldo_caixa": float(saldo_caixa),
            "contas_receber": float(contas_receber),
            "total_fiado_devedor": float(contas_receber),
            "contas_pagar": float(contas_pagar),
            "clientes": clientes,
            "fornecedores": fornecedores,
            "produtos": produtos,
            "estoque_baixo": estoque_baixo,
            "contas_vencidas_qtd": int(vencidas[0]),
            "contas_vencidas_valor": float(vencidas[1]),
            "contas_vencendo_hoje_qtd": int(vencendo_hoje[0]),
            "contas_vencendo_hoje_valor": float(vencendo_hoje[1]),
            "contas_pagas_hoje_qtd": int(pagas_hoje[0]),
            "contas_pagas_hoje_valor": float(pagas_hoje[1]),
            "fiado_recebido_hoje": float(fiado_recebido_hoje),
            "contas_mes_pago": float(contas_mes_pago),
            "contas_mes_pendente": float(contas_mes_pendente),
            "serie_recebimentos_mensal": serie_recebimentos_mensal,
            "serie_pagamentos_mensal": serie_pagamentos_mensal,
        }