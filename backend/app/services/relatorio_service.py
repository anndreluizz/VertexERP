from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.venda import Venda
from app.models.item_venda import ItemVenda
from app.models.produto import Produto
from app.models.cliente import Cliente


class RelatorioService:

    @staticmethod
    def vendas_geral(
        db: Session,
        data_inicio: date,
        data_fim: date,
        cliente_id: int | None = None,
        produto_id: int | None = None,
        categoria: str | None = None,
        forma_pagamento: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        inicio = datetime.combine(data_inicio, time.min)
        fim = datetime.combine(data_fim, time.min) + timedelta(days=1)

        duracao = fim - inicio
        inicio_anterior = inicio - duracao
        fim_anterior = inicio

        filtros = dict(
            cliente_id=cliente_id,
            produto_id=produto_id,
            categoria=categoria,
            forma_pagamento=forma_pagamento,
            status=status,
        )

        kpis_atual = RelatorioService._kpis(db, inicio, fim, **filtros)
        kpis_anterior = RelatorioService._kpis(
            db, inicio_anterior, fim_anterior, **filtros
        )

        vendas_total, vendas = RelatorioService._listar_vendas(
            db, inicio, fim, skip=skip, limit=limit, **filtros
        )

        return {
            "receita_total": RelatorioService._kpi_valor(
                kpis_atual["receita_total"], kpis_anterior["receita_total"]
            ),
            "lucro": RelatorioService._kpi_valor(
                kpis_atual["lucro"], kpis_anterior["lucro"]
            ),
            "quantidade_vendas": RelatorioService._kpi_valor(
                kpis_atual["quantidade_vendas"],
                kpis_anterior["quantidade_vendas"],
            ),
            "ticket_medio": RelatorioService._kpi_valor(
                kpis_atual["ticket_medio"], kpis_anterior["ticket_medio"]
            ),
            "clientes_atendidos": RelatorioService._kpi_valor(
                kpis_atual["clientes_atendidos"],
                kpis_anterior["clientes_atendidos"],
            ),
            "produtos_vendidos": RelatorioService._kpi_valor(
                kpis_atual["produtos_vendidos"],
                kpis_anterior["produtos_vendidos"],
            ),
            "margem_lucro": RelatorioService._kpi_valor(
                kpis_atual["margem_lucro"], kpis_anterior["margem_lucro"]
            ),
            "vendas_por_dia": RelatorioService._vendas_por_dia(
                db, inicio, fim, **filtros
            ),
            "top_produtos": RelatorioService._top_produtos(
                db, inicio, fim, **filtros
            ),
            "formas_pagamento": RelatorioService._formas_pagamento(
                db, inicio, fim, **filtros
            ),
            "vendas_total": vendas_total,
            "vendas": vendas,
        }

    # ==================================================
    # IDS DAS VENDAS NO ESCOPO (aplica todos os filtros)
    # ==================================================

    @staticmethod
    def _ids_vendas(
        db,
        inicio,
        fim,
        cliente_id=None,
        produto_id=None,
        categoria=None,
        forma_pagamento=None,
        status=None,
    ):
        query = db.query(Venda.id).filter(
            Venda.data >= inicio,
            Venda.data < fim,
            Venda.status == (status or "FINALIZADA"),
        )

        if cliente_id is not None:
            query = query.filter(Venda.cliente_id == cliente_id)

        if forma_pagamento is not None:
            query = query.filter(Venda.forma_pagamento == forma_pagamento)

        if produto_id is not None or categoria is not None:
            query = query.join(
                ItemVenda, ItemVenda.venda_id == Venda.id
            ).join(
                Produto, ItemVenda.produto_id == Produto.id
            )

            if produto_id is not None:
                query = query.filter(Produto.id == produto_id)

            if categoria is not None:
                query = query.filter(Produto.categoria == categoria)

        return [linha[0] for linha in query.distinct().all()]

    # ==================================================
    # KPIs
    # ==================================================

    @staticmethod
    def _kpis(
        db,
        inicio,
        fim,
        cliente_id=None,
        produto_id=None,
        categoria=None,
        forma_pagamento=None,
        status=None,
    ):
        ids = RelatorioService._ids_vendas(
            db, inicio, fim, cliente_id, produto_id,
            categoria, forma_pagamento, status,
        )

        if not ids:
            return {
                "receita_total": Decimal("0"),
                "lucro": Decimal("0"),
                "quantidade_vendas": 0,
                "ticket_medio": Decimal("0"),
                "clientes_atendidos": 0,
                "produtos_vendidos": 0,
                "margem_lucro": Decimal("0"),
            }

        receita_total = (
            db.query(func.coalesce(func.sum(Venda.valor_total), 0))
            .filter(Venda.id.in_(ids))
            .scalar()
        )

        quantidade_vendas = len(ids)

        clientes_atendidos = (
            db.query(func.count(func.distinct(Venda.cliente_id)))
            .filter(Venda.id.in_(ids), Venda.cliente_id.isnot(None))
            .scalar()
        )

        itens_query = (
            db.query(ItemVenda, Produto.preco_custo)
            .join(Produto, ItemVenda.produto_id == Produto.id)
            .filter(ItemVenda.venda_id.in_(ids))
        )

        if produto_id is not None:
            itens_query = itens_query.filter(Produto.id == produto_id)

        if categoria is not None:
            itens_query = itens_query.filter(Produto.categoria == categoria)

        itens = itens_query.all()

        lucro = sum(
            (item.valor_unitario - (preco_custo or 0)) * item.quantidade
            for item, preco_custo in itens
        )

        produtos_vendidos = sum(item.quantidade for item, _ in itens)

        ticket_medio = (
            receita_total / quantidade_vendas
            if quantidade_vendas else Decimal("0")
        )

        margem_lucro = (
            (lucro / receita_total * 100) if receita_total else Decimal("0")
        )

        return {
            "receita_total": receita_total,
            "lucro": lucro,
            "quantidade_vendas": quantidade_vendas,
            "ticket_medio": ticket_medio,
            "clientes_atendidos": clientes_atendidos,
            "produtos_vendidos": produtos_vendidos,
            "margem_lucro": margem_lucro,
        }

    @staticmethod
    def _kpi_valor(atual, anterior):
        if anterior:
            variacao_pct = (atual - anterior) / anterior * 100
        else:
            variacao_pct = None

        return {
            "atual": atual,
            "anterior": anterior,
            "variacao_pct": variacao_pct,
        }

    # ==================================================
    # VENDAS POR DIA (gráfico)
    # ==================================================

    @staticmethod
    def _vendas_por_dia(
        db,
        inicio,
        fim,
        cliente_id=None,
        produto_id=None,
        categoria=None,
        forma_pagamento=None,
        status=None,
    ):
        ids = RelatorioService._ids_vendas(
            db, inicio, fim, cliente_id, produto_id,
            categoria, forma_pagamento, status,
        )

        if not ids:
            return []

        resultados = (
            db.query(
                func.date(Venda.data).label("dia"),
                func.sum(Venda.valor_total),
            )
            .filter(Venda.id.in_(ids))
            .group_by("dia")
            .order_by("dia")
            .all()
        )

        return [
            {"data": str(dia), "total": float(total)}
            for dia, total in resultados
        ]

    # ==================================================
    # TOP PRODUTOS (gráfico)
    # ==================================================

    @staticmethod
    def _top_produtos(
        db,
        inicio,
        fim,
        cliente_id=None,
        produto_id=None,
        categoria=None,
        forma_pagamento=None,
        status=None,
        limite=5,
    ):
        ids = RelatorioService._ids_vendas(
            db, inicio, fim, cliente_id, produto_id,
            categoria, forma_pagamento, status,
        )

        if not ids:
            return []

        query = (
            db.query(
                Produto.nome,
                func.sum(ItemVenda.quantidade),
                func.sum(ItemVenda.subtotal),
            )
            .join(Produto, ItemVenda.produto_id == Produto.id)
            .filter(ItemVenda.venda_id.in_(ids))
        )

        if produto_id is not None:
            query = query.filter(Produto.id == produto_id)

        if categoria is not None:
            query = query.filter(Produto.categoria == categoria)

        resultados = (
            query.group_by(Produto.nome)
            .order_by(func.sum(ItemVenda.quantidade).desc())
            .limit(limite)
            .all()
        )

        return [
            {"produto": nome, "quantidade": int(quantidade), "total": float(total)}
            for nome, quantidade, total in resultados
        ]

    # ==================================================
    # FORMAS DE PAGAMENTO (gráfico)
    # ==================================================

    @staticmethod
    def _formas_pagamento(
        db,
        inicio,
        fim,
        cliente_id=None,
        produto_id=None,
        categoria=None,
        forma_pagamento=None,
        status=None,
    ):
        ids = RelatorioService._ids_vendas(
            db, inicio, fim, cliente_id, produto_id,
            categoria, forma_pagamento, status,
        )

        if not ids:
            return []

        resultados = (
            db.query(
                Venda.forma_pagamento,
                func.count(Venda.id),
                func.sum(Venda.valor_total),
            )
            .filter(Venda.id.in_(ids))
            .group_by(Venda.forma_pagamento)
            .order_by(func.sum(Venda.valor_total).desc())
            .all()
        )

        return [
            {
                "forma_pagamento": forma,
                "quantidade": int(quantidade),
                "total": float(total),
            }
            for forma, quantidade, total in resultados
        ]

    # ==================================================
    # TABELA DETALHADA (paginada)
    # ==================================================

    @staticmethod
    def _listar_vendas(
        db,
        inicio,
        fim,
        cliente_id=None,
        produto_id=None,
        categoria=None,
        forma_pagamento=None,
        status=None,
        skip=0,
        limit=100,
    ):
        ids = RelatorioService._ids_vendas(
            db, inicio, fim, cliente_id, produto_id,
            categoria, forma_pagamento, status,
        )

        if not ids:
            return 0, []

        base = (
            db.query(Venda, Cliente.nome)
            .outerjoin(Cliente, Venda.cliente_id == Cliente.id)
            .filter(Venda.id.in_(ids))
        )

        total = base.count()

        resultados = (
            base.order_by(Venda.data.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        vendas = [
            {
                "id": venda.id,
                "data": venda.data,
                "cliente": nome_cliente,
                "valor_total": venda.valor_total,
                "forma_pagamento": venda.forma_pagamento,
                "status": venda.status,
            }
            for venda, nome_cliente in resultados
        ]

        return total, vendas
