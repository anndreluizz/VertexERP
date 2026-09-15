from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.venda import Venda
from app.models.item_venda import ItemVenda
from app.models.produto import Produto
from app.models.cliente import Cliente
from app.services.venda_service import _parcelas_pagamento


class RelatorioService:

    @staticmethod
    def vendas_geral(
        db: Session,
        data_inicio: date | None,
        data_fim: date,
        cliente_id: int | None = None,
        produto_id: int | None = None,
        categoria: str | None = None,
        forma_pagamento: str | None = None,
        status: str | None = None,
        loja_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
        top_produtos_limite: int = 5,
        top_produtos_ordenar_por: str = "quantidade",
    ):
        # data_inicio None = "Tudo" (sem limite inferior), usado pela
        # tela de Relatórios > Financeiro -- nesse caso não existe uma
        # janela "período anterior" que faça sentido pra comparar (não
        # dá pra comparar "tudo" com "o período antes de tudo"), então
        # kpis_anterior fica zerado sem rodar a query de comparação
        # (_kpi_valor já trata anterior=0 como "sem comparação").
        inicio = (
            datetime.combine(data_inicio, time.min)
            if data_inicio is not None else None
        )
        fim = datetime.combine(data_fim, time.min) + timedelta(days=1)

        filtros = dict(
            cliente_id=cliente_id,
            produto_id=produto_id,
            categoria=categoria,
            forma_pagamento=forma_pagamento,
            status=status,
            loja_id=loja_id,
        )

        kpis_atual = RelatorioService._kpis(db, inicio, fim, **filtros)

        if inicio is not None:
            duracao = fim - inicio
            inicio_anterior = inicio - duracao
            fim_anterior = inicio
            kpis_anterior = RelatorioService._kpis(
                db, inicio_anterior, fim_anterior, **filtros
            )
        else:
            kpis_anterior = {
                "receita_total": 0, "lucro": 0, "quantidade_vendas": 0,
                "ticket_medio": 0, "clientes_atendidos": 0,
                "produtos_vendidos": 0, "margem_lucro": 0,
            }

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
                db, inicio, fim,
                limite=top_produtos_limite,
                ordenar_por=top_produtos_ordenar_por,
                **filtros,
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
        loja_id=None,
    ):
        query = db.query(Venda.id).filter(
            Venda.status == (status or "FINALIZADA"),
        )

        # inicio None = sem limite inferior ("Tudo", ver
        # RelatorioService.vendas_geral) -- em vez de simular isso com
        # uma data fixa hardcoded, que descartaria vendas reais
        # anteriores a ela e forcaria um calculo de janela de
        # comparacao sem sentido
        if inicio is not None:
            query = query.filter(Venda.data >= inicio)

        if fim is not None:
            query = query.filter(Venda.data < fim)

        if cliente_id is not None:
            query = query.filter(Venda.cliente_id == cliente_id)

        if loja_id is not None:
            query = query.filter(Venda.loja_id == loja_id)

        if forma_pagamento is not None:
            # uma venda dividida em 2 formas (ver forma_pagamento_2)
            # precisa aparecer no filtro pela forma que ela usou na
            # segunda parcela tambem, senao um pagamento
            # metade-dinheiro-metade-pix filtrado por "PIX" some do
            # relatorio mesmo tendo recebido PIX de verdade
            query = query.filter(
                or_(
                    Venda.forma_pagamento == forma_pagamento,
                    Venda.forma_pagamento_2 == forma_pagamento,
                )
            )

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
        loja_id=None,
    ):
        ids = RelatorioService._ids_vendas(
            db, inicio, fim, cliente_id, produto_id,
            categoria, forma_pagamento, status, loja_id,
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
        loja_id=None,
    ):
        ids = RelatorioService._ids_vendas(
            db, inicio, fim, cliente_id, produto_id,
            categoria, forma_pagamento, status, loja_id,
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
        loja_id=None,
        limite=5,
        ordenar_por="quantidade",
    ):
        ids = RelatorioService._ids_vendas(
            db, inicio, fim, cliente_id, produto_id,
            categoria, forma_pagamento, status, loja_id,
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

        # "quantidade" (padrão) é o critério de "mais vendido" usado pelo
        # PDV/Dashboard; a aba Financeiro dos Relatórios pede "valor" pra
        # manter o ranking por faturamento que a tela já mostrava antes
        # de migrar pra este endpoint agregado.
        ordenacao = (
            func.sum(ItemVenda.subtotal).desc()
            if ordenar_por == "valor"
            else func.sum(ItemVenda.quantidade).desc()
        )

        # agrupa por id (chave real) e nao so por nome -- Produto.nome
        # nao tem constraint unique, entao dois produtos distintos com
        # o mesmo nome (ex.: um recadastrado apos descontinuar o
        # antigo) nao podem ter a receita mesclada num unico item do
        # ranking
        resultados = (
            query.group_by(Produto.id, Produto.nome)
            .order_by(ordenacao)
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
        loja_id=None,
    ):
        ids = RelatorioService._ids_vendas(
            db, inicio, fim, cliente_id, produto_id,
            categoria, forma_pagamento, status, loja_id,
        )

        if not ids:
            return []

        # nao da pra so agrupar por Venda.forma_pagamento e somar
        # valor_total: numa venda dividida em 2 formas (ver
        # forma_pagamento_2/valor_forma_2), o total inteiro iria pra
        # forma principal e a segunda forma ficaria de fora -- usa o
        # mesmo _parcelas_pagamento que o resto do sistema (criar/
        # cancelar venda) ja usa pra nao inventar uma segunda logica
        # de split que pode divergir da de verdade
        vendas = (
            db.query(Venda)
            .filter(Venda.id.in_(ids))
            .all()
        )

        agregados: dict[str, dict] = {}

        for venda in vendas:
            for forma_parcela, valor_parcela in _parcelas_pagamento(
                venda, venda.valor_total
            ):
                bucket = agregados.setdefault(
                    forma_parcela, {"quantidade": 0, "total": Decimal("0")}
                )
                bucket["quantidade"] += 1
                bucket["total"] += valor_parcela

        return sorted(
            (
                {
                    "forma_pagamento": forma,
                    "quantidade": dados["quantidade"],
                    "total": float(dados["total"]),
                }
                for forma, dados in agregados.items()
            ),
            key=lambda item: item["total"],
            reverse=True,
        )

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
        loja_id=None,
        skip=0,
        limit=100,
    ):
        ids = RelatorioService._ids_vendas(
            db, inicio, fim, cliente_id, produto_id,
            categoria, forma_pagamento, status, loja_id,
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
