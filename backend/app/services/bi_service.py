"""Inteligencia de Negocios: junta num resumo so' os numeros que o dono
precisa pra decidir (vendas, fiado, contas, caixa, lojas), sempre
calculados aqui a partir dos registros -- nunca estimados por IA.

Reaproveita os calculos de RelatorioService (mesmo faturamento, mesmas
formas de pagamento das telas de Relatorios) e soma o que faltava:
idade das dividas de fiado, contas por vencimento, previsao de 30 dias
e avisos de dados incompletos."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.caixa import Caixa
from app.models.cliente import Cliente
from app.models.conta_pagar import ContaPagar
from app.models.item_venda import ItemVenda
from app.models.loja import Loja
from app.models.movimento_caixa import MovimentoCaixa
from app.models.movimento_fiado import MovimentoFiado
from app.models.produto import Produto
from app.models.venda import Venda
from app.services.relatorio_service import RelatorioService, _devolvido_por_venda

FORMAS_A_PRAZO = {"PRAZO"}
CODIGO_PRODUTO_GENERICO = "PLANILHA"  # vendas lancadas depois, sem itens reais
HISTORICO_MINIMO_DIAS = 60
# faixas de atraso do fiado (dias desde a compra mais antiga ainda em aberto)
FAIXAS_ATRASO = [(0, 30), (31, 60), (61, 90), (91, 180), (181, None)]

_ZERO = Decimal("0")
_EPSILON = Decimal("0.009")


def _compra_mais_antiga_em_aberto(movimentos):
    """FIFO do caderno de fiado: cada pagamento/haver abate as compras
    mais antigas primeiro. Mesma regra de frontend/services/
    cliente_analise._fifo_pagamentos (tela de Clientes)."""
    # ponytail: copia da regra do frontend (e do app); se mudar la, mudar aqui
    compras = sorted(
        ([m.data, m.valor] for m in movimentos if m.tipo == "COMPRA"),
        key=lambda c: c[0],
    )
    abatimentos = sum(
        (m.valor for m in movimentos if m.tipo != "COMPRA"), _ZERO
    )
    for compra in compras:
        if abatimentos >= compra[1]:
            abatimentos -= compra[1]
            continue
        return compra[0]
    return None


class BiService:

    @staticmethod
    def resumo(db: Session, data_inicio: date, data_fim: date, loja_id: int | None = None):
        if data_fim < data_inicio:
            raise ValueError("A data final não pode ser antes da inicial.")

        inicio = datetime.combine(data_inicio, time.min)
        fim = datetime.combine(data_fim, time.min) + timedelta(days=1)
        agora = datetime.now()

        loja_nome = "Todas as lojas"
        if loja_id is not None:
            loja = db.get(Loja, loja_id)
            if not loja:
                raise ValueError("Loja não encontrada.")
            loja_nome = loja.nome

        vendas = BiService._vendas(db, inicio, fim, loja_id)
        recebido_fiado = BiService._recebido_fiado(db, inicio, fim, loja_id)
        fiado = BiService._fiado(db, agora)
        contas = BiService._contas_pagar(db, inicio, fim, agora, loja_id)
        gavetas = BiService._dinheiro_nas_gavetas(db, loja_id)
        avisos, qualidade = BiService._avisos(db, loja_id, fiado)

        resultado = {
            "periodo": {
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "dias": (data_fim - data_inicio).days + 1,
                "loja_id": loja_id,
                "loja_nome": loja_nome,
                "gerado_em": agora,
            },
            "vendas": vendas,
            "recebimentos": {"fiado_recebido": recebido_fiado},
            "fiado": fiado,
            "contas_pagar": contas,
            "caixa": {"dinheiro_nas_gavetas": gavetas},
            "previsao_30_dias": BiService._previsao(db, agora, loja_id, gavetas, contas),
            "lojas": BiService._lojas(db, inicio, fim, agora) if loja_id is None else [],
            "avisos": avisos,
            "qualidade_dados": qualidade,
        }
        resultado["recomendacoes"] = recomendacoes(resultado)
        return resultado

    # ---------------- vendas ----------------

    @staticmethod
    def _vendas(db, inicio, fim, loja_id):
        kpis = RelatorioService._kpis(db, inicio, fim, loja_id=loja_id)
        formas = RelatorioService._formas_pagamento(db, inicio, fim, loja_id=loja_id)
        ids = RelatorioService._ids_vendas(db, inicio, fim, loja_id=loja_id)
        devolvido = sum(_devolvido_por_venda(db, ids).values(), _ZERO) if ids else _ZERO

        a_prazo = sum(
            (Decimal(str(f["total"])) for f in formas if f["forma_pagamento"] in FORMAS_A_PRAZO),
            _ZERO,
        )
        liquido = kpis["receita_total"]

        return {
            "faturamento_bruto": liquido + devolvido,
            "devolucoes": devolvido,
            "faturamento_liquido": liquido,
            "quantidade": kpis["quantidade_vendas"],
            "ticket_medio": Decimal(kpis["ticket_medio"]).quantize(Decimal("0.01")),
            "a_vista": liquido - a_prazo,
            "a_prazo": a_prazo,
            "formas_pagamento": formas,
            "lucro_bruto": None if kpis["custo_incompleto"] else kpis["lucro"],
            "custo_incompleto": kpis["custo_incompleto"],
            "mais_vendidos": [
                p for p in RelatorioService._top_produtos(
                    db, inicio, fim, loja_id=loja_id, limite=11, ordenar_por="valor"
                )
                if p["produto"] != BiService._nome_generico(db)
            ][:10],
            "produtos_sem_venda": BiService._produtos_sem_venda(db, ids),
        }

    @staticmethod
    def _nome_generico(db):
        return db.query(Produto.nome).filter(
            Produto.codigo == CODIGO_PRODUTO_GENERICO
        ).limit(1).scalar()

    @staticmethod
    def _produtos_sem_venda(db, ids):
        vendidos = (
            db.query(ItemVenda.produto_id).filter(ItemVenda.venda_id.in_(ids))
            if ids else None
        )
        query = db.query(Produto.nome, Produto.estoque).filter(Produto.ativo.is_(True))
        if vendidos is not None:
            query = query.filter(Produto.id.notin_(vendidos))
        linhas = query.order_by(Produto.estoque.desc()).all()
        return {
            "quantidade": len(linhas),
            "exemplos": [{"produto": n, "estoque": e} for n, e in linhas[:10]],
        }

    # ---------------- fiado ----------------

    @staticmethod
    def _recebido_fiado(db, inicio, fim, loja_id):
        """Pelo lancamento no caixa (tem loja e ja inclui correcoes); fiado
        abatido sem dinheiro (haver) nao e' dinheiro recebido."""
        query = (
            db.query(func.coalesce(func.sum(MovimentoCaixa.valor), 0))
            .join(Caixa, Caixa.id == MovimentoCaixa.caixa_id)
            .filter(
                MovimentoCaixa.tipo == "RECEBIMENTO_FIADO",
                MovimentoCaixa.data >= inicio,
                MovimentoCaixa.data < fim,
            )
        )
        if loja_id is not None:
            query = query.filter(Caixa.loja_id == loja_id)
        return query.scalar()

    @staticmethod
    def _fiado(db, agora):
        """Da empresa toda: o caderno de fiado nao e' separado por loja
        (dividas antigas foram migradas sem loja)."""
        movimentos_por_cliente: dict[int, list] = {}
        for m in db.query(MovimentoFiado).all():
            movimentos_por_cliente.setdefault(m.cliente_id, []).append(m)

        clientes = {
            c.id: c for c in db.query(Cliente).filter(
                Cliente.id.in_(movimentos_por_cliente.keys())
            )
        } if movimentos_por_cliente else {}

        faixas = [
            {"de_dias": de, "ate_dias": ate, "clientes": 0, "total": _ZERO}
            for de, ate in FAIXAS_ATRASO
        ]
        devedores = []

        for cliente_id, movs in movimentos_por_cliente.items():
            saldo = sum(
                (m.valor if m.tipo == "COMPRA" else -m.valor for m in movs), _ZERO
            )
            if saldo <= _EPSILON:
                continue
            desde = _compra_mais_antiga_em_aberto(movs)
            dias = max((agora - desde).days, 0) if desde else 0
            cliente = clientes.get(cliente_id)
            pagamentos = [m.data for m in movs if m.tipo == "PAGAMENTO"]
            devedores.append({
                "cliente_id": cliente_id,
                "nome": cliente.nome if cliente else f"Cliente #{cliente_id}",
                "saldo": saldo,
                "dias_em_atraso": dias,
                "ultimo_pagamento": max(pagamentos) if pagamentos else None,
                "tem_telefone": bool(cliente and (cliente.telefone or "").strip()),
                "limite_credito": cliente.limite_credito if cliente else None,
            })
            for faixa in faixas:
                if dias >= faixa["de_dias"] and (faixa["ate_dias"] is None or dias <= faixa["ate_dias"]):
                    faixa["clientes"] += 1
                    faixa["total"] += saldo
                    break

        devedores.sort(key=lambda d: d["saldo"], reverse=True)

        return {
            "saldo_em_aberto": sum((d["saldo"] for d in devedores), _ZERO),
            "clientes_devendo": len(devedores),
            "faixas_atraso": faixas,
            "maiores_devedores": devedores[:15],
            "devedores_sem_telefone": sum(1 for d in devedores if not d["tem_telefone"]),
            "acima_do_limite": sum(
                1 for d in devedores
                if d["limite_credito"] is not None and d["saldo"] > d["limite_credito"]
            ),
        }

    # ---------------- contas a pagar ----------------

    @staticmethod
    def _contas_pagar(db, inicio, fim, agora, loja_id):
        hoje = datetime.combine(agora.date(), time.min)
        pendentes = db.query(ContaPagar).filter(ContaPagar.status == "PENDENTE")
        pagas = db.query(func.coalesce(func.sum(ContaPagar.valor), 0)).filter(
            ContaPagar.status == "PAGO",
            ContaPagar.data_pagamento >= inicio,
            ContaPagar.data_pagamento < fim,
        )
        if loja_id is not None:
            pendentes = pendentes.filter(ContaPagar.loja_id == loja_id)
            pagas = pagas.filter(ContaPagar.loja_id == loja_id)

        def faixa(contas):
            return {"quantidade": len(contas), "total": sum((c.valor for c in contas), _ZERO)}

        todas = pendentes.all()
        vencidas = [c for c in todas if c.data_vencimento < hoje]
        ate_7 = [c for c in todas if hoje <= c.data_vencimento < hoje + timedelta(days=8)]
        ate_30 = [c for c in todas if hoje <= c.data_vencimento < hoje + timedelta(days=31)]

        return {
            "vencidas": faixa(vencidas),
            "proximos_7_dias": faixa(ate_7),
            "proximos_30_dias": faixa(ate_30),
            "pendentes_total": faixa(todas),
            "pagas_no_periodo": pagas.scalar(),
            "proximas": [
                {
                    "id": c.id,
                    "descricao": c.descricao,
                    "vencimento": c.data_vencimento.date(),
                    "valor": c.valor,
                    "categoria": c.categoria,
                }
                for c in sorted(vencidas + ate_30, key=lambda c: c.data_vencimento)[:15]
            ],
        }

    # ---------------- caixa e previsao ----------------

    @staticmethod
    def _dinheiro_nas_gavetas(db, loja_id):
        query = db.query(func.coalesce(func.sum(Caixa.saldo_final), 0)).filter(
            Caixa.status == "ABERTO"
        )
        if loja_id is not None:
            query = query.filter(Caixa.loja_id == loja_id)
        return query.scalar()

    @staticmethod
    def _previsao(db, agora, loja_id, gavetas, contas):
        """Entradas = media diaria do que entrou de verdade (vendas a vista
        + fiado recebido) nos ultimos 30 dias, vezes 30. So' uma
        referencia: nao promete que vai vender igual."""
        fim = datetime.combine(agora.date(), time.min) + timedelta(days=1)
        primeira = db.query(func.min(Venda.data)).filter(Venda.status == "FINALIZADA")
        if loja_id is not None:
            primeira = primeira.filter(Venda.loja_id == loja_id)
        primeira = primeira.scalar()

        if primeira is None:
            dias_base = 0
            media_diaria = _ZERO
        else:
            dias_base = min(30, max((agora - primeira).days + 1, 1))
            inicio = fim - timedelta(days=dias_base)
            vendas = BiService._vendas_a_vista(db, inicio, fim, loja_id)
            fiado = Decimal(BiService._recebido_fiado(db, inicio, fim, loja_id))
            media_diaria = (vendas + fiado) / dias_base

        entradas = (media_diaria * 30).quantize(Decimal("0.01"))
        saidas = contas["vencidas"]["total"] + contas["proximos_30_dias"]["total"]

        return {
            "entradas_estimadas": entradas,
            "media_diaria_entradas": media_diaria.quantize(Decimal("0.01")),
            "dias_de_base": dias_base,
            "saidas_previstas": saidas,
            "dinheiro_nas_gavetas": gavetas,
            "saldo_previsto": Decimal(gavetas) + entradas - saidas,
            "observacao": (
                "Entradas estimadas pela média do que entrou de verdade "
                f"(vendas à vista + fiado recebido) nos últimos {dias_base} dias. "
                "Saídas = contas pendentes vencidas e com vencimento nos "
                "próximos 30 dias. Não inclui saldo bancário (não registrado)."
            ),
        }

    @staticmethod
    def _vendas_a_vista(db, inicio, fim, loja_id):
        formas = RelatorioService._formas_pagamento(db, inicio, fim, loja_id=loja_id)
        return sum(
            (Decimal(str(f["total"])) for f in formas if f["forma_pagamento"] not in FORMAS_A_PRAZO),
            _ZERO,
        )

    # ---------------- lojas ----------------

    @staticmethod
    def _lojas(db, inicio, fim, agora):
        resultado = []
        for loja in db.query(Loja).filter(Loja.ativa.is_(True)).order_by(Loja.id):
            loja_id = loja.id
            vendas = BiService._vendas(db, inicio, fim, loja_id)
            contas = BiService._contas_pagar(db, inicio, fim, agora, loja_id)
            resultado.append({
                "loja_id": loja_id,
                "loja_nome": loja.nome,
                "faturamento_liquido": vendas["faturamento_liquido"],
                "quantidade": vendas["quantidade"],
                "ticket_medio": vendas["ticket_medio"],
                "a_vista": vendas["a_vista"],
                "a_prazo": vendas["a_prazo"],
                "fiado_recebido": BiService._recebido_fiado(db, inicio, fim, loja_id),
                "contas_pagas_no_periodo": contas["pagas_no_periodo"],
                "contas_pendentes_30_dias": (
                    contas["vencidas"]["total"] + contas["proximos_30_dias"]["total"]
                ),
                "dinheiro_nas_gavetas": BiService._dinheiro_nas_gavetas(db, loja_id),
            })
        return resultado

    # ---------------- qualidade dos dados ----------------

    @staticmethod
    def _avisos(db, loja_id, fiado):
        avisos = []
        ativos = db.query(Produto).filter(Produto.ativo.is_(True))
        total_ativos = ativos.count()
        sem_custo = ativos.filter(func.coalesce(Produto.preco_custo, 0) <= 0).count()
        sem_minimo = ativos.filter(func.coalesce(Produto.estoque_minimo, 0) <= 0).count()

        if sem_custo:
            avisos.append(
                f"{sem_custo} de {total_ativos} produtos ativos sem custo cadastrado: "
                "lucro e margem não podem ser calculados."
            )
        if sem_minimo:
            avisos.append(
                f"{sem_minimo} de {total_ativos} produtos ativos sem estoque mínimo: "
                "a sugestão de reposição fica incompleta."
            )

        genericas = (
            db.query(func.count(func.distinct(ItemVenda.venda_id)))
            .join(Produto, Produto.id == ItemVenda.produto_id)
            .filter(Produto.codigo == CODIGO_PRODUTO_GENERICO)
            .scalar()
        )
        if genericas:
            avisos.append(
                f"{genericas} vendas foram lançadas depois sem os produtos "
                "(produto genérico \"PLANILHA\"): ficam fora do ranking de produtos."
            )

        primeira = db.query(func.min(Venda.data)).filter(Venda.status == "FINALIZADA")
        if loja_id is not None:
            primeira = primeira.filter(Venda.loja_id == loja_id)
        primeira = primeira.scalar()
        dias_historico = (datetime.now() - primeira).days + 1 if primeira else 0
        if primeira is None:
            avisos.append("Nenhuma venda registrada ainda.")
        elif (datetime.now() - primeira).days < HISTORICO_MINIMO_DIAS:
            avisos.append(
                f"Histórico de vendas começa em {primeira:%d/%m/%Y}: "
                f"menos de {HISTORICO_MINIMO_DIAS} dias, tendências ainda não são confiáveis."
            )

        if fiado["devedores_sem_telefone"]:
            avisos.append(
                f"{fiado['devedores_sem_telefone']} de {fiado['clientes_devendo']} "
                "clientes devendo não têm telefone cadastrado."
            )
        sem_loja = db.query(ContaPagar).filter(
            ContaPagar.status == "PENDENTE", ContaPagar.loja_id.is_(None)
        ).count()
        if sem_loja:
            avisos.append(
                f"{sem_loja} contas a pagar pendentes sem loja: entram só no "
                "total de todas as lojas (sem regra pra dividir entre unidades)."
            )
        if loja_id is not None:
            avisos.append(
                "O fiado é da empresa toda: o caderno não separa por loja "
                "(dívidas antigas foram migradas sem loja)."
            )
        return avisos, {
            "produtos_ativos": total_ativos,
            "produtos_sem_custo": sem_custo,
            "produtos_sem_estoque_minimo": sem_minimo,
            "vendas_sem_produto": genericas,
            "dias_de_historico": dias_historico,
        }


# ==================================================
# RECOMENDACOES (regras fixas sobre os numeros ja calculados -- nada
# aqui e' estimado por IA; cada uma diz de onde veio o numero)
# ==================================================

ORDEM_PRIORIDADE = {"critica": 0, "alta": 1, "media": 2, "baixa": 3}
PARTICIPACAO_A_PRAZO_ALTA = Decimal("0.5")
RECEBIMENTO_MINIMO_DO_VENDIDO_A_PRAZO = Decimal("0.5")
VENDAS_MINIMAS_PRA_CONCLUIR = 20


def _brl(valor):
    texto = f"{Decimal(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _pct(parte, todo):
    return f"{Decimal(parte) / Decimal(todo) * 100:.0f}%"


def recomendacoes(r):
    """Transforma o resumo em acoes pro dono. Recebe o dict de
    BiService.resumo (sem banco), entao cada regra e' testavel sozinha."""
    lista = []
    periodo = r["periodo"]
    rotulo = (
        f"{periodo['data_inicio']:%d/%m/%Y} a {periodo['data_fim']:%d/%m/%Y} "
        f"({periodo['loja_nome']})"
    )
    vendas, fiado, contas = r["vendas"], r["fiado"], r["contas_pagar"]
    prev, qualidade = r["previsao_30_dias"], r["qualidade_dados"]

    def add(prioridade, problema, evidencias, impacto, acao, prazo, indicador):
        lista.append({
            "prioridade": prioridade, "problema": problema, "evidencias": evidencias,
            "impacto": impacto, "acao": acao, "prazo": prazo, "indicador": indicador,
        })

    if contas["vencidas"]["quantidade"]:
        add(
            "critica", "Há contas a pagar vencidas.",
            [f"{contas['vencidas']['quantidade']} contas vencidas somando "
             f"{_brl(contas['vencidas']['total'])} (contas a pagar pendentes)."],
            "Juros, multa e risco de corte ou protesto.",
            "Pagar ou renegociar as vencidas antes das próximas; ligar para o "
            "fornecedor e pedir novo vencimento quando não houver dinheiro.",
            "Hoje", "Contas vencidas = R$ 0,00",
        )

    if prev["dias_de_base"] and Decimal(prev["saldo_previsto"]) < 0:
        sete_dias = Decimal(contas["proximos_7_dias"]["total"])
        cabe_na_semana = (
            Decimal(prev["dinheiro_nas_gavetas"]) + Decimal(prev["media_diaria_entradas"]) * 7
        )
        maiores = sorted(contas["proximas"], key=lambda c: c["valor"], reverse=True)[:3]
        add(
            "critica" if sete_dias > cabe_na_semana else "alta",
            "A previsão de pagamentos dos próximos 30 dias supera as entradas estimadas.",
            [
                f"Saídas previstas: {_brl(prev['saidas_previstas'])} (contas vencidas e "
                "com vencimento em até 30 dias).",
                f"Entradas estimadas: {_brl(prev['entradas_estimadas'])} (média de "
                f"{_brl(prev['media_diaria_entradas'])}/dia dos últimos "
                f"{prev['dias_de_base']} dias).",
                f"Dinheiro nas gavetas agora: {_brl(prev['dinheiro_nas_gavetas'])}.",
                f"Falta estimada: {_brl(-Decimal(prev['saldo_previsto']))}.",
            ] + [
                f"Conta próxima: {c['descricao'] or 'sem descrição'}, "
                f"{_brl(c['valor'])} em {c['vencimento']:%d/%m}." for c in maiores
            ],
            "Risco de faltar dinheiro para pagar as contas. A estimativa não inclui "
            "saldo bancário (não registrado no sistema).",
            "Priorizar a cobrança dos maiores devedores do fiado, tentar adiar ou "
            "parcelar as maiores contas acima e segurar despesas que podem esperar.",
            "Esta semana", "Saldo previsto em 30 dias maior ou igual a R$ 0,00",
        )

    antigas = [f for f in fiado["faixas_atraso"] if f["de_dias"] > 90]
    total_antigo = sum((Decimal(f["total"]) for f in antigas), _ZERO)
    if total_antigo > 0:
        clientes_antigos = sum(f["clientes"] for f in antigas)
        alvos = [d for d in fiado["maiores_devedores"] if d["dias_em_atraso"] > 90][:5]
        add(
            "alta", "Fiado com mais de 90 dias em aberto.",
            [f"{clientes_antigos} clientes devem há mais de 90 dias, somando "
             f"{_brl(total_antigo)} de {_brl(fiado['saldo_em_aberto'])} em aberto "
             "(caderno de fiado, empresa toda)."]
            + [f"{d['nome']}: {_brl(d['saldo'])}, compra mais antiga em aberto há "
               f"{d['dias_em_atraso']} dias." for d in alvos],
            "Quanto mais antiga a dívida, menor a chance de receber.",
            "Cobrar primeiro os maiores valores mais antigos; oferecer parcelamento "
            "em vez de esperar o valor inteiro. Envio de cobrança só com sua autorização.",
            "Próximos 15 dias", "Fiado com mais de 90 dias (R$)",
        )

    a_prazo = Decimal(vendas["a_prazo"])
    recebido = Decimal(r["recebimentos"]["fiado_recebido"])
    if (
        a_prazo > 0 and periodo["dias"] >= 7
        and recebido < a_prazo * RECEBIMENTO_MINIMO_DO_VENDIDO_A_PRAZO
    ):
        add(
            "alta", "O fiado está crescendo: entra menos do que se vende a prazo.",
            [f"Vendido a prazo em {rotulo}: {_brl(a_prazo)}.",
             f"Fiado recebido no mesmo período: {_brl(recebido)} "
             f"({_pct(recebido, a_prazo)} do vendido a prazo)."],
            f"A dívida dos clientes aumentou cerca de {_brl(a_prazo - recebido)} no período.",
            "Combinar data de pagamento em toda venda a prazo e cobrar no vencimento; "
            "segurar novas vendas a prazo para quem está atrasado.",
            "Próximos 30 dias", "Fiado recebido dividido pelo vendido a prazo (meta 100%)",
        )

    escopos = r["lojas"] or [{"loja_nome": periodo["loja_nome"], **vendas}]
    for loja in escopos:
        liquido = Decimal(loja["faturamento_liquido"])
        if loja["quantidade"] < VENDAS_MINIMAS_PRA_CONCLUIR or liquido <= 0:
            continue
        if Decimal(loja["a_prazo"]) / liquido > PARTICIPACAO_A_PRAZO_ALTA:
            add(
                "alta", f"{loja['loja_nome']}: a maior parte das vendas é a prazo.",
                [f"A prazo: {_brl(loja['a_prazo'])} de {_brl(liquido)} vendidos em "
                 f"{periodo['data_inicio']:%d/%m/%Y} a {periodo['data_fim']:%d/%m/%Y} "
                 f"({_pct(loja['a_prazo'], liquido)}), em {loja['quantidade']} vendas."],
                "Venda a prazo não vira dinheiro no caixa até o cliente pagar.",
                "Incentivar pagamento à vista (PIX/dinheiro) e vender a prazo só "
                "dentro do limite de crédito de cada cliente.",
                "Próximos 30 dias", "% das vendas a prazo",
            )

    if fiado["acima_do_limite"]:
        add(
            "media", "Clientes com dívida acima do limite de crédito.",
            [f"{fiado['acima_do_limite']} clientes devem mais do que o limite cadastrado."],
            "Mais venda a prazo para quem já passou do limite aumenta o risco de não receber.",
            "Revisar esses clientes antes de vender a prazo de novo. O sistema avisa, "
            "mas não bloqueia sozinho; mudar limite ou bloquear só com sua decisão.",
            "Próximos 15 dias", "Clientes acima do limite",
        )

    if fiado["devedores_sem_telefone"]:
        sem_tel = [d for d in fiado["maiores_devedores"] if not d["tem_telefone"]][:5]
        add(
            "media", "Clientes devendo sem telefone cadastrado.",
            [f"{fiado['devedores_sem_telefone']} de {fiado['clientes_devendo']} clientes "
             "com saldo em aberto não têm telefone."]
            + [f"{d['nome']}: {_brl(d['saldo'])}." for d in sem_tel],
            "Sem contato não há como cobrar nem lembrar do vencimento.",
            "Pedir e cadastrar o telefone na próxima vez que o cliente vier, "
            "começando pelos maiores saldos.",
            "Próximos 30 dias", "Devedores sem telefone",
        )

    if qualidade["produtos_sem_custo"]:
        add(
            "media", "Produtos sem custo cadastrado.",
            [f"{qualidade['produtos_sem_custo']} de {qualidade['produtos_ativos']} "
             "produtos ativos sem preço de custo."],
            "Sem custo não dá para saber o lucro nem quais produtos dão mais margem.",
            "Cadastrar o custo (nota do fornecedor) começando pelos produtos que mais vendem.",
            "Próximos 30 dias", "Produtos sem custo",
        )

    if qualidade["produtos_sem_estoque_minimo"]:
        add(
            "baixa", "Produtos sem estoque mínimo.",
            [f"{qualidade['produtos_sem_estoque_minimo']} de {qualidade['produtos_ativos']} "
             "produtos ativos sem estoque mínimo."],
            "O sistema não consegue avisar quando repor.",
            "Definir o estoque mínimo dos produtos que vendem com frequência.",
            "Próximos 30 dias", "Produtos sem estoque mínimo",
        )

    parados = [p for p in vendas["produtos_sem_venda"]["exemplos"] if p["estoque"] > 0]
    if parados and periodo["dias"] >= 30 and qualidade["dias_de_historico"] >= 30:
        add(
            "baixa", "Produtos com estoque e sem venda no período.",
            [f"{vendas['produtos_sem_venda']['quantidade']} produtos ativos sem venda "
             f"em {rotulo}."]
            + [f"{p['produto']}: {p['estoque']} em estoque." for p in parados[:5]],
            "Dinheiro parado em mercadoria.",
            "Avaliar promoção, combo ou exposição melhor para esses itens.",
            "Próximos 30 dias", "Produtos sem venda no período",
        )

    lista.sort(key=lambda x: ORDEM_PRIORIDADE[x["prioridade"]])
    return lista
