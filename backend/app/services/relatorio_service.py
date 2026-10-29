from calendar import monthrange
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.enums.status_venda import StatusVenda
from app.models.venda import Venda
from app.models.item_venda import ItemVenda
from app.models.produto import Produto
from app.models.cliente import Cliente
from app.models.loja import Loja
from app.models.estoque_loja import EstoqueLoja
from app.models.compra import Compra
from app.models.fornecedor import Fornecedor
from app.models.conta_pagar import ContaPagar
from app.models.devolucao import Devolucao, ItemDevolucao
from app.services.caixa_service import CaixaService
from app.services.venda_service import _parcelas_pagamento


def _devolvido_por_venda(db, ids):
    """{venda_id: valor devolvido} -- devolucao/troca conta contra a
    venda original (mesmo criterio da tela de Vendas, ver
    VendaService.resumo_vendedores), pra receita do relatorio bater
    com o que ficou de verdade."""
    if not ids:
        return {}
    linhas = (
        db.query(Devolucao.venda_id, func.sum(Devolucao.valor_total))
        .filter(Devolucao.venda_id.in_(ids))
        .group_by(Devolucao.venda_id)
        .all()
    )
    return {venda_id: valor or Decimal("0") for venda_id, valor in linhas}


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
            "custo_incompleto": kpis_atual["custo_incompleto"],
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
    # COMPARATIVO ENTRE LOJAS (matriz x filial etc.)
    # ==================================================

    @staticmethod
    def mes_a_mes(db: Session, ano: int, loja_id: int | None = None):
        """Quadro do ano, um item por mes (ate o mes atual): as mesmas
        contas do Relatorios > Financeiro (_kpis) e do Relatorios > Caixa
        (CaixaService.entradas), pra os numeros baterem com essas telas."""
        hoje = date.today()
        ultimo = 12 if ano < hoje.year else (hoje.month if ano == hoje.year else 0)
        meses = []
        for mes in range(1, ultimo + 1):
            inicio = date(ano, mes, 1)
            fim = date(ano, mes, monthrange(ano, mes)[1])
            k = RelatorioService._kpis(
                db, datetime.combine(inicio, time.min),
                datetime.combine(fim, time.min) + timedelta(days=1),
                loja_id=loja_id,
            )
            e = CaixaService.entradas(db, inicio, fim, loja_id)
            meses.append({
                "mes": mes,
                "faturamento": k["receita_total"],
                "quantidade_vendas": k["quantidade_vendas"],
                "ticket_medio": k["ticket_medio"],
                "lucro": k["lucro"],
                "custo_incompleto": k["custo_incompleto"],
                "entrou": e["total"],
                "vendido_fiado": e["vendas_prazo"],
                "fiado_recebido": e["fiado_recebido"],
                "contas_pagas": e["contas_pagas"],
                "sangrias": e["sangrias"],
                "sobrou": e["sobrou"],
            })
        return meses

    @staticmethod
    def comparativo_lojas(
        db: Session,
        data_inicio: date | None,
        data_fim: date,
    ):
        """Mesmos KPIs de vendas_geral, um conjunto por loja ativa --
        pensado pra comparar desempenho entre lojas lado a lado (ex.:
        matriz x filial), sem precisar trocar o filtro de loja e olhar
        os números um de cada vez."""

        inicio = (
            datetime.combine(data_inicio, time.min)
            if data_inicio is not None else None
        )
        fim = datetime.combine(data_fim, time.min) + timedelta(days=1)

        lojas = (
            db.query(Loja)
            .filter(Loja.ativa.is_(True))
            .order_by(Loja.id)
            .all()
        )

        resultado = []

        for loja in lojas:
            kpis = RelatorioService._kpis(db, inicio, fim, loja_id=loja.id)

            resultado.append({
                "loja_id": loja.id,
                "loja_nome": loja.nome,
                "receita_total": kpis["receita_total"],
                "lucro": kpis["lucro"],
                "quantidade_vendas": kpis["quantidade_vendas"],
                "ticket_medio": kpis["ticket_medio"],
                "margem_lucro": kpis["margem_lucro"],
                "custo_incompleto": kpis["custo_incompleto"],
            })

        return resultado

    # ==================================================
    # FUNIL DE VENDAS (carrinho aberto agora x finalizadas/canceladas
    # no periodo)
    # ==================================================

    @staticmethod
    def funil_vendas(
        db: Session,
        data_inicio: date | None,
        data_fim: date,
        loja_id: int | None = None,
    ):
        """Nao existe uma cadeia real ABERTA->FINALIZADA->CANCELADA por
        venda: uma venda suspensa (ABERTA) retomada vira uma Venda NOVA
        ao ser finalizada (ver VendaService.criar/suspender), o
        rascunho original e' so' apagado -- entao "carrinhos em aberto"
        e' uma contagem AO VIVO (agora), sem recorte de periodo, ja que
        rascunhos excluidos nao deixam rastro. Finalizadas/canceladas
        sim sao do periodo pedido (mesmo Venda.data de todo o resto
        deste service)."""

        inicio = (
            datetime.combine(data_inicio, time.min)
            if data_inicio is not None else None
        )
        fim = datetime.combine(data_fim, time.min) + timedelta(days=1)

        query = db.query(Venda.status, func.count(Venda.id)).filter(
            Venda.status.in_([
                StatusVenda.FINALIZADA.value,
                StatusVenda.CANCELADA.value,
            ]),
            Venda.data < fim,
        )

        if inicio is not None:
            query = query.filter(Venda.data >= inicio)

        if loja_id is not None:
            query = query.filter(Venda.loja_id == loja_id)

        contagens = dict(query.group_by(Venda.status).all())

        finalizadas = contagens.get(StatusVenda.FINALIZADA.value, 0)
        canceladas = contagens.get(StatusVenda.CANCELADA.value, 0)
        total = finalizadas + canceladas

        suspensas_query = db.query(func.count(Venda.id)).filter(
            Venda.status == StatusVenda.ABERTA.value
        )

        if loja_id is not None:
            suspensas_query = suspensas_query.filter(Venda.loja_id == loja_id)

        return {
            "suspensas_agora": suspensas_query.scalar() or 0,
            "finalizadas": finalizadas,
            "canceladas": canceladas,
            "taxa_cancelamento": (
                round(canceladas / total * 100, 2) if total else 0
            ),
        }

    # ==================================================
    # MARGEM POR CATEGORIA
    # ==================================================

    @staticmethod
    def margem_por_categoria(
        db: Session,
        data_inicio: date | None,
        data_fim: date,
        loja_id: int | None = None,
    ):
        inicio = (
            datetime.combine(data_inicio, time.min)
            if data_inicio is not None else None
        )
        fim = datetime.combine(data_fim, time.min) + timedelta(days=1)

        ids = RelatorioService._ids_vendas(db, inicio, fim, loja_id=loja_id)

        if not ids:
            return []

        itens = (
            db.query(ItemVenda, Produto.categoria, Produto.preco_custo)
            .join(Produto, ItemVenda.produto_id == Produto.id)
            .filter(ItemVenda.venda_id.in_(ids))
            .all()
        )

        agregados: dict[str, dict] = {}

        for item, categoria, preco_custo in itens:
            chave = categoria or "Sem categoria"
            bucket = agregados.setdefault(
                chave, {"receita": Decimal("0"), "lucro": Decimal("0"), "quantidade": 0,
                        "custo_incompleto": False}
            )
            bucket["custo_incompleto"] |= not preco_custo
            bucket["receita"] += item.subtotal
            bucket["lucro"] += (
                item.valor_unitario - (preco_custo or 0)
            ) * item.quantidade
            bucket["quantidade"] += item.quantidade

        resultado = [
            {
                "categoria": categoria,
                "receita": dados["receita"],
                "lucro": dados["lucro"],
                "margem_pct": (
                    round(dados["lucro"] / dados["receita"] * 100, 2)
                    if dados["receita"] else Decimal("0")
                ),
                "quantidade": dados["quantidade"],
                "custo_incompleto": dados["custo_incompleto"],
            }
            for categoria, dados in agregados.items()
        ]

        return sorted(resultado, key=lambda r: r["receita"], reverse=True)

    # ==================================================
    # ESTOQUE POR CATEGORIA (valor parado em estoque, pelo custo)
    # ==================================================

    @staticmethod
    def estoque_por_categoria(db: Session, loja_id: int | None = None):
        # sem loja_id = soma todas as lojas juntas (visao "quanto a
        # empresa toda tem parado", nao uma linha por loja -- pra
        # comparar loja a loja ja existe comparativo_estoque_lojas)
        query = (
            db.query(EstoqueLoja, Produto.categoria, Produto.preco_custo)
            .join(Produto, EstoqueLoja.produto_id == Produto.id)
        )

        if loja_id is not None:
            query = query.filter(EstoqueLoja.loja_id == loja_id)

        agregados: dict[str, dict] = {}

        for estoque, categoria, preco_custo in query.all():
            chave = categoria or "Sem categoria"
            bucket = agregados.setdefault(
                chave, {"quantidade": 0, "valor": Decimal("0")}
            )
            bucket["quantidade"] += estoque.quantidade
            bucket["valor"] += Decimal(estoque.quantidade) * (preco_custo or 0)

        resultado = [
            {
                "categoria": categoria,
                "quantidade": dados["quantidade"],
                "valor": dados["valor"],
            }
            for categoria, dados in agregados.items()
        ]

        return sorted(resultado, key=lambda r: r["valor"], reverse=True)

    # ==================================================
    # VENDAS POR DIA DA SEMANA
    # ==================================================

    _DIAS_SEMANA = [
        "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo",
    ]

    @staticmethod
    def vendas_por_dia_semana(
        db: Session,
        data_inicio: date | None,
        data_fim: date,
        loja_id: int | None = None,
    ):
        inicio = (
            datetime.combine(data_inicio, time.min)
            if data_inicio is not None else None
        )
        fim = datetime.combine(data_fim, time.min) + timedelta(days=1)

        ids = RelatorioService._ids_vendas(db, inicio, fim, loja_id=loja_id)

        agregados = [
            {"quantidade": 0, "total": Decimal("0")} for _ in range(7)
        ]

        if ids:
            for data, valor_total in (
                db.query(Venda.data, Venda.valor_total)
                .filter(Venda.id.in_(ids))
                .all()
            ):
                indice = data.weekday()
                agregados[indice]["quantidade"] += 1
                agregados[indice]["total"] += valor_total

        return [
            {
                "dia_semana": RelatorioService._DIAS_SEMANA[i],
                "quantidade": agregados[i]["quantidade"],
                "total": agregados[i]["total"],
            }
            for i in range(7)
        ]

    # ==================================================
    # VENDAS POR DIA DA SEMANA X HORA (heatmap)
    # ==================================================

    @staticmethod
    def vendas_dia_semana_hora(
        db: Session,
        data_inicio: date | None,
        data_fim: date,
        loja_id: int | None = None,
    ):
        inicio = (
            datetime.combine(data_inicio, time.min)
            if data_inicio is not None else None
        )
        fim = datetime.combine(data_fim, time.min) + timedelta(days=1)

        ids = RelatorioService._ids_vendas(db, inicio, fim, loja_id=loja_id)

        # matriz 7 (dia da semana) x 24 (hora) -- agregados[dia][hora]
        agregados = [
            [{"quantidade": 0, "total": Decimal("0")} for _ in range(24)]
            for _ in range(7)
        ]

        if ids:
            for data, valor_total in (
                db.query(Venda.data, Venda.valor_total)
                .filter(Venda.id.in_(ids))
                .all()
            ):
                celula = agregados[data.weekday()][data.hour]
                celula["quantidade"] += 1
                celula["total"] += valor_total

        return [
            {
                "dia_semana": RelatorioService._DIAS_SEMANA[dia],
                "hora": hora,
                "quantidade": agregados[dia][hora]["quantidade"],
                "total": agregados[dia][hora]["total"],
            }
            for dia in range(7)
            for hora in range(24)
        ]

    # ==================================================
    # COMPRAS / FORNECEDORES
    # ==================================================

    @staticmethod
    def gasto_compras_mensal(
        db: Session,
        data_inicio: date | None,
        data_fim: date,
    ):
        inicio = (
            datetime.combine(data_inicio, time.min)
            if data_inicio is not None else None
        )
        fim = datetime.combine(data_fim, time.min) + timedelta(days=1)

        query = db.query(Compra.data, Compra.valor_total).filter(
            Compra.status == "FINALIZADA",
            Compra.data < fim,
        )

        if inicio is not None:
            query = query.filter(Compra.data >= inicio)

        agregados: dict[str, Decimal] = {}

        for data, valor_total in query.all():
            chave = data.strftime("%Y-%m")
            agregados[chave] = agregados.get(chave, Decimal("0")) + valor_total

        return [
            {"mes": mes, "total": total}
            for mes, total in sorted(agregados.items())
        ]

    @staticmethod
    def ranking_fornecedores(
        db: Session,
        data_inicio: date | None,
        data_fim: date,
        limite: int = 10,
    ):
        inicio = (
            datetime.combine(data_inicio, time.min)
            if data_inicio is not None else None
        )
        fim = datetime.combine(data_fim, time.min) + timedelta(days=1)

        query = (
            db.query(
                Fornecedor.id,
                Fornecedor.razao_social,
                Fornecedor.nome_fantasia,
                func.count(Compra.id),
                func.coalesce(func.sum(Compra.valor_total), 0),
            )
            .join(Compra, Compra.fornecedor_id == Fornecedor.id)
            .filter(Compra.status == "FINALIZADA", Compra.data < fim)
        )

        if inicio is not None:
            query = query.filter(Compra.data >= inicio)

        resultados = (
            query.group_by(
                Fornecedor.id, Fornecedor.razao_social, Fornecedor.nome_fantasia
            )
            .order_by(func.coalesce(func.sum(Compra.valor_total), 0).desc())
            .limit(limite)
            .all()
        )

        return [
            {
                "fornecedor_id": fid,
                "nome": nome_fantasia or razao_social,
                "quantidade_compras": quantidade,
                "total": total,
            }
            for fid, razao_social, nome_fantasia, quantidade, total in resultados
        ]

    @staticmethod
    def prazo_medio_pagamento_fornecedores(db: Session):
        """Media de dias entre a data da compra e o vencimento de cada
        parcela gerada (so' compras a prazo, que geram ContaPagar com
        compra_id preenchido -- ver ContaPagarService.criar_compra_prazo),
        por fornecedor."""

        resultados = (
            db.query(
                Fornecedor.id,
                Fornecedor.razao_social,
                Fornecedor.nome_fantasia,
                ContaPagar.data_vencimento,
                Compra.data,
            )
            .join(Compra, ContaPagar.compra_id == Compra.id)
            .join(Fornecedor, Compra.fornecedor_id == Fornecedor.id)
            .filter(ContaPagar.compra_id.isnot(None))
            .all()
        )

        dias_por_fornecedor: dict[int, list[int]] = {}
        nomes: dict[int, str] = {}

        for fid, razao_social, nome_fantasia, vencimento, data_compra in resultados:
            dias_por_fornecedor.setdefault(fid, []).append(
                (vencimento - data_compra).days
            )
            nomes[fid] = nome_fantasia or razao_social

        resultado = [
            {
                "fornecedor_id": fid,
                "nome": nomes[fid],
                "prazo_medio_dias": round(sum(dias) / len(dias), 1),
                "quantidade_parcelas": len(dias),
            }
            for fid, dias in dias_por_fornecedor.items()
        ]

        return sorted(resultado, key=lambda r: r["prazo_medio_dias"], reverse=True)

    # ==================================================
    # CATEGORIAS SEM VENDA HA MUITO TEMPO
    # ==================================================

    @staticmethod
    def categorias_sem_venda(db: Session, dias: int = 90):

        limite = datetime.now() - timedelta(days=dias)

        todas_categorias = {
            categoria for (categoria,) in
            db.query(Produto.categoria)
            .filter(Produto.ativo.is_(True), Produto.categoria.isnot(None))
            .distinct()
            .all()
        }

        ultima_por_categoria = dict(
            db.query(Produto.categoria, func.max(Venda.data))
            .join(ItemVenda, ItemVenda.produto_id == Produto.id)
            .join(Venda, ItemVenda.venda_id == Venda.id)
            .filter(
                Venda.status == StatusVenda.FINALIZADA.value,
                Produto.categoria.isnot(None),
            )
            .group_by(Produto.categoria)
            .all()
        )

        resultado = []

        for categoria in todas_categorias:

            ultima_venda = ultima_por_categoria.get(categoria)

            if ultima_venda is not None and ultima_venda >= limite:
                continue

            resultado.append({
                "categoria": categoria,
                "ultima_venda": ultima_venda,
                "dias_sem_venda": (
                    (datetime.now() - ultima_venda).days
                    if ultima_venda is not None else None
                ),
            })

        return sorted(
            resultado,
            key=lambda r: (
                r["dias_sem_venda"] if r["dias_sem_venda"] is not None
                else float("inf")
            ),
            reverse=True,
        )

    # ==================================================
    # CURVA ABC (classificacao de produto por receita)
    # ==================================================

    @staticmethod
    def curva_abc(
        db: Session,
        data_inicio: date | None,
        data_fim: date,
        loja_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        """Classifica cada produto pela participacao acumulada na
        receita do periodo: A = ate 80% da receita acumulada, B = ate
        95%, C = o resto -- classificacao classica de curva ABC, usada
        pra saber quais produtos merecem mais atencao (giro, reposicao,
        negociacao com fornecedor)."""

        inicio = (
            datetime.combine(data_inicio, time.min)
            if data_inicio is not None else None
        )
        fim = datetime.combine(data_fim, time.min) + timedelta(days=1)

        ids = RelatorioService._ids_vendas(db, inicio, fim, loja_id=loja_id)

        if not ids:
            return []

        resultados = (
            db.query(
                Produto.id,
                Produto.nome,
                func.sum(ItemVenda.quantidade),
                func.sum(ItemVenda.subtotal),
            )
            .join(Produto, ItemVenda.produto_id == Produto.id)
            .filter(ItemVenda.venda_id.in_(ids))
            .group_by(Produto.id, Produto.nome)
            .order_by(func.sum(ItemVenda.subtotal).desc())
            .all()
        )

        receita_total = sum(float(total) for _, _, _, total in resultados)

        if receita_total <= 0:
            return []

        itens = []
        acumulado = 0.0

        for produto_id, nome, quantidade, total in resultados:
            total = float(total)
            percentual = (total / receita_total) * 100
            acumulado += percentual

            if acumulado <= 80:
                classe = "A"
            elif acumulado <= 95:
                classe = "B"
            else:
                classe = "C"

            itens.append({
                "produto_id": produto_id,
                "produto": nome,
                "quantidade": quantidade,
                "total": total,
                "percentual": round(percentual, 2),
                "percentual_acumulado": round(acumulado, 2),
                "classe": classe,
            })

        return itens[skip:skip + limit]

    # ==================================================
    # COMPARATIVO DE ESTOQUE ENTRE LOJAS
    # ==================================================

    @staticmethod
    def comparativo_estoque_lojas(db: Session):
        """Mesmo espirito de comparativo_lojas, mas de estoque fisico
        em vez de vendas -- quantidade total, valor parado em estoque
        (pelo custo) e quantos produtos estao abaixo do minimo, um
        conjunto por loja ativa."""

        lojas = (
            db.query(Loja)
            .filter(Loja.ativa.is_(True))
            .order_by(Loja.id)
            .all()
        )

        resultado = []

        for loja in lojas:
            linhas = (
                db.query(EstoqueLoja, Produto.preco_custo)
                .join(Produto, EstoqueLoja.produto_id == Produto.id)
                .filter(EstoqueLoja.loja_id == loja.id)
                .all()
            )

            quantidade_total = sum(e.quantidade for e, _ in linhas)
            valor_em_estoque = sum(
                float(e.quantidade) * float(preco_custo)
                for e, preco_custo in linhas
            )
            produtos_abaixo_minimo = sum(
                1 for e, _ in linhas if e.quantidade <= e.estoque_minimo
            )

            resultado.append({
                "loja_id": loja.id,
                "loja_nome": loja.nome,
                "quantidade_total": quantidade_total,
                "valor_em_estoque": valor_em_estoque,
                "produtos_abaixo_minimo": produtos_abaixo_minimo,
            })

        return resultado

    # ==================================================
    # SUGESTAO DE REPOSICAO (esboco v1 -- so' lista quem esta abaixo do
    # minimo e sugere completar ate o minimo; NAO e' um motor de compra
    # automatica, nao considera lead time de fornecedor, sazonalidade,
    # nem gera pedido nenhum sozinho)
    # ==================================================

    @staticmethod
    def sugestao_reposicao(
        db: Session,
        loja_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        if loja_id is not None:
            linhas = (
                db.query(EstoqueLoja, Produto.nome)
                .join(Produto, EstoqueLoja.produto_id == Produto.id)
                .filter(
                    EstoqueLoja.loja_id == loja_id,
                    EstoqueLoja.quantidade <= EstoqueLoja.estoque_minimo,
                )
                .all()
            )

            itens = [
                {
                    "produto_id": e.produto_id,
                    "produto": nome,
                    "quantidade_atual": e.quantidade,
                    "estoque_minimo": e.estoque_minimo,
                    "quantidade_sugerida": max(
                        0, e.estoque_minimo - e.quantidade
                    ),
                }
                for e, nome in linhas
            ]
        else:
            produtos = (
                db.query(Produto)
                .filter(
                    Produto.ativo.is_(True),
                    Produto.estoque <= Produto.estoque_minimo,
                )
                .all()
            )

            itens = [
                {
                    "produto_id": p.id,
                    "produto": p.nome,
                    "quantidade_atual": p.estoque,
                    "estoque_minimo": p.estoque_minimo,
                    "quantidade_sugerida": max(
                        0, p.estoque_minimo - p.estoque
                    ),
                }
                for p in produtos
            ]

        # mais critico primeiro (quem tem menos proporcao do minimo
        # ainda em estoque, ou ja zerado)
        itens.sort(
            key=lambda i: (
                i["quantidade_atual"] / i["estoque_minimo"]
                if i["estoque_minimo"] else 0
            )
        )

        return itens[skip:skip + limit]

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
                "custo_incompleto": False,
            }

        receita_total = (
            db.query(func.coalesce(func.sum(Venda.valor_total), 0))
            .filter(Venda.id.in_(ids))
            .scalar()
        )

        # filtro por produto/categoria ja soma a venda inteira (nao so os
        # itens filtrados), entao so desconta devolucao sem esse filtro
        if produto_id is None and categoria is None:
            receita_total -= sum(_devolvido_por_venda(db, ids).values(), Decimal("0"))

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

        # pecas devolvidas saem do lucro e das pecas vendidas
        devolvidos_query = (
            db.query(ItemDevolucao, Produto.preco_custo)
            .join(Devolucao, Devolucao.id == ItemDevolucao.devolucao_id)
            .join(Produto, ItemDevolucao.produto_id == Produto.id)
            .filter(Devolucao.venda_id.in_(ids))
        )
        if produto_id is not None:
            devolvidos_query = devolvidos_query.filter(Produto.id == produto_id)
        if categoria is not None:
            devolvidos_query = devolvidos_query.filter(Produto.categoria == categoria)
        for item_dev, preco_custo in devolvidos_query.all():
            lucro -= item_dev.valor - (preco_custo or 0) * item_dev.quantidade
            produtos_vendidos -= item_dev.quantidade

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
            # produto vendido sem custo cadastrado conta custo 0 e o
            # "lucro" vira o faturamento -- a tela mostra "—" em vez disso
            "custo_incompleto": any(not custo for _, custo in itens),
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

        devolvido = _devolvido_por_venda(db, ids)
        por_dia: dict = {}
        for venda_id, data, total in (
            db.query(Venda.id, Venda.data, Venda.valor_total)
            .filter(Venda.id.in_(ids))
            .all()
        ):
            dia = data.date()
            por_dia[dia] = por_dia.get(dia, Decimal("0")) + total - devolvido.get(venda_id, 0)

        return [
            {"data": str(dia), "total": float(total)}
            for dia, total in sorted(por_dia.items())
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
            {"produto": nome, "quantidade": quantidade, "total": float(total)}
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
        devolvido = _devolvido_por_venda(db, ids)

        for venda in vendas:
            # devolucao desconta proporcional de cada forma da venda
            fator = (
                (venda.valor_total - devolvido.get(venda.id, 0)) / venda.valor_total
                if venda.valor_total else Decimal("1")
            )
            for forma_parcela, valor_parcela in _parcelas_pagamento(
                venda, venda.valor_total
            ):
                bucket = agregados.setdefault(
                    forma_parcela, {"quantidade": 0, "total": Decimal("0")}
                )
                bucket["quantidade"] += 1
                bucket["total"] += valor_parcela * fator

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
