from datetime import datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QScrollArea,
    QFrame,
)

from design import tokens
from design.widgets import CardKPI, SecaoCard, Badge
from design.charts import GraficoArea, LinhaProgresso
from widgets.nav_card import NavCard

from services.api import dashboard, me
from services.venda_service import listar_vendas
from services.produto_service import listar_produtos
from services.conta_pagar_service import listar_contas_pagar

from telas.relatorios import NOMES_FORMA_PAGAMENTO, CORES_FORMA_PAGAMENTO


DIAS_SEMANA_ABREV = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

VARIANTE_BADGE_FORMA = {
    "DINHEIRO": "sucesso",
    "PIX": "info",
    "DEBITO": "neutro",
    "CREDITO": "neutro",
    "BOLETO": "neutro",
    "PRAZO": "alerta",
}


def _formatar_moeda(valor):
    return (
        f"R$ {float(valor):,.2f}".replace(",", "X")
        .replace(".", ",").replace("X", ".")
    )


def _parse_data(texto):
    try:
        return datetime.fromisoformat(texto)
    except (ValueError, TypeError):
        return None


class Dashboard(QWidget):

    navegar_pdv = Signal()
    navegar_estoque = Signal()
    navegar_caixa = Signal()

    def __init__(self):

        super().__init__()

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        conteudo = QWidget()
        conteudo.setStyleSheet("background:transparent;")

        self.layout_principal = QVBoxLayout(conteudo)
        self.layout_principal.setContentsMargins(28, 24, 28, 28)
        self.layout_principal.setSpacing(20)

        scroll.setWidget(conteudo)
        layout_externo.addWidget(scroll)

        # ======================
        # SAUDAÇÃO
        # ======================

        self.lbl_saudacao = QLabel()
        self.lbl_saudacao.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)
        self.layout_principal.addWidget(self.lbl_saudacao)

        # ======================
        # ATALHOS
        # ======================

        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(16)

        self.card_pdv = NavCard(
            "Frente de Caixa", "Venda rápida (F3)",
            tokens.PRIMARIA, "#1E3A8A", icone_nome="shopping-cart",
        )
        self.card_estoque = NavCard(
            "Estoque", "Gestão de itens",
            tokens.SECUNDARIA, "#0D7A4B", icone_nome="package",
        )
        self.card_caixa = NavCard(
            "Caixa", "Abertura e fechamento",
            tokens.ALERTA, "#C2660B", icone_nome="wallet",
        )

        self.card_pdv.clicado.connect(self.navegar_pdv.emit)
        self.card_estoque.clicado.connect(self.navegar_estoque.emit)
        self.card_caixa.clicado.connect(self.navegar_caixa.emit)

        nav_layout.addWidget(self.card_pdv)
        nav_layout.addWidget(self.card_estoque)
        nav_layout.addWidget(self.card_caixa)

        self.layout_principal.addLayout(nav_layout)

        # ======================
        # KPIs
        # ======================

        grid_kpi = QGridLayout()
        grid_kpi.setSpacing(16)

        self.kpi_faturamento = CardKPI("Faturamento Hoje", "dollar-sign", tokens.PRIMARIA)
        self.kpi_lucro = CardKPI("Lucro Hoje", "trending-up", tokens.SECUNDARIA)
        self.kpi_ticket = CardKPI("Ticket Médio", "shopping-cart", tokens.PRIMARIA)
        self.kpi_pedidos = CardKPI("Pedidos Hoje", "file-text", tokens.PRIMARIA)
        self.kpi_caixa = CardKPI("Fluxo de Caixa", "wallet", tokens.SECUNDARIA)
        self.kpi_clientes = CardKPI("Clientes", "users", tokens.PRIMARIA)
        self.kpi_produtos = CardKPI("Produtos", "package", tokens.PRIMARIA)
        self.kpi_estoque = CardKPI("Estoque em Alerta", "alert-triangle", tokens.ALERTA)

        cartoes_kpi = [
            self.kpi_faturamento, self.kpi_lucro, self.kpi_ticket, self.kpi_pedidos,
            self.kpi_caixa, self.kpi_clientes, self.kpi_produtos, self.kpi_estoque,
        ]

        for i, card in enumerate(cartoes_kpi):
            grid_kpi.addWidget(card, i // 4, i % 4)

        for coluna in range(4):
            grid_kpi.setColumnStretch(coluna, 1)

        self.layout_principal.addLayout(grid_kpi)

        # ======================
        # GRÁFICO + FORMAS DE PAGAMENTO
        # ======================

        linha_graficos = QHBoxLayout()
        linha_graficos.setSpacing(16)

        self.secao_grafico = SecaoCard("Vendas — últimos 7 dias", "bar-chart-2")
        self.grafico = GraficoArea()
        self.secao_grafico.corpo.addWidget(self.grafico)

        self.secao_pagamentos = SecaoCard("Formas de Pagamento", "credit-card")
        self.secao_pagamentos.setMinimumWidth(280)

        linha_graficos.addWidget(self.secao_grafico, stretch=6)
        linha_graficos.addWidget(self.secao_pagamentos, stretch=4)

        self.layout_principal.addLayout(linha_graficos)

        # ======================
        # TOP PRODUTOS + VENDAS RECENTES + ALERTAS
        # ======================

        linha_listas = QHBoxLayout()
        linha_listas.setSpacing(16)

        self.secao_top_produtos = SecaoCard("Top Produtos", "package")
        self.secao_vendas_recentes = SecaoCard("Vendas Recentes", "shopping-cart")
        self.secao_alertas = SecaoCard("Alertas", "alert-triangle")

        linha_listas.addWidget(self.secao_top_produtos, stretch=1)
        linha_listas.addWidget(self.secao_vendas_recentes, stretch=1)
        linha_listas.addWidget(self.secao_alertas, stretch=1)

        self.layout_principal.addLayout(linha_listas)

        self.layout_principal.addStretch()

        self.carregar()

    # ======================================
    # CARREGAMENTO DE DADOS
    # ======================================

    def carregar(self):

        usuario = me()
        nome_usuario = usuario.get("nome") or "Usuário"
        self.lbl_saudacao.setText(f"Olá, {nome_usuario}! Aqui está o resumo de hoje.")

        dados = dashboard()
        vendas = listar_vendas()
        produtos = listar_produtos()

        try:
            contas_pagar = listar_contas_pagar()
        except Exception:
            contas_pagar = []

        produtos_por_id = {p["id"]: p for p in produtos}
        vendas_finalizadas = [v for v in vendas if v.get("status") == "FINALIZADA"]

        self._atualizar_kpis(dados, vendas_finalizadas, produtos_por_id)
        self._atualizar_grafico(vendas_finalizadas)
        self._atualizar_formas_pagamento(vendas_finalizadas)
        self._atualizar_top_produtos(vendas_finalizadas, produtos_por_id)
        self._atualizar_vendas_recentes(vendas_finalizadas)
        self._atualizar_alertas(produtos, contas_pagar)

    def _atualizar_kpis(self, dados, vendas_finalizadas, produtos_por_id):

        vendas_hoje = float(dados.get("vendas_hoje", 0) or 0)
        vendas_hoje_qtd = int(dados.get("vendas_hoje_qtd", 0) or 0)

        self.kpi_faturamento.definir_valor(_formatar_moeda(vendas_hoje))
        self.kpi_pedidos.definir_valor(str(vendas_hoje_qtd))

        ticket_medio = (vendas_hoje / vendas_hoje_qtd) if vendas_hoje_qtd else 0
        self.kpi_ticket.definir_valor(_formatar_moeda(ticket_medio))

        self.kpi_caixa.definir_valor(_formatar_moeda(dados.get("saldo_caixa", 0) or 0))
        self.kpi_clientes.definir_valor(str(dados.get("clientes", 0)))
        self.kpi_produtos.definir_valor(str(dados.get("produtos", 0)))
        self.kpi_estoque.definir_valor(str(dados.get("estoque_baixo", 0)))

        # lucro bruto de hoje: (preço de venda - custo) por item, só das
        # vendas de hoje — nao vem pronto do /dashboard, entao calcula
        # aqui em cima do preco_custo de cada produto.
        hoje = datetime.now().date()
        lucro_hoje = 0.0

        for venda in vendas_finalizadas:

            data_venda = _parse_data(venda.get("data"))

            if data_venda is None or data_venda.date() != hoje:
                continue

            for item in venda.get("itens", []):

                produto = produtos_por_id.get(item.get("produto_id"))
                custo = float(produto.get("preco_custo", 0)) if produto else 0.0
                valor_unit = float(item.get("valor_unitario", 0))

                lucro_hoje += (valor_unit - custo) * item.get("quantidade", 0)

        self.kpi_lucro.definir_valor(_formatar_moeda(lucro_hoje))

    def _atualizar_grafico(self, vendas_finalizadas):

        hoje = datetime.now().date()

        rotulos = []
        valores = []

        for i in range(6, -1, -1):

            dia = hoje - timedelta(days=i)

            total_dia = sum(
                float(v.get("valor_total", 0))
                for v in vendas_finalizadas
                if (_parse_data(v.get("data")) or datetime.min).date() == dia
            )

            rotulos.append(DIAS_SEMANA_ABREV[dia.weekday()])
            valores.append(total_dia)

        self.grafico.definir_dados(rotulos, valores)

    def _atualizar_formas_pagamento(self, vendas_finalizadas):

        hoje = datetime.now().date()
        inicio_mes = hoje.replace(day=1)

        totais_forma = {}

        for venda in vendas_finalizadas:

            data_venda = _parse_data(venda.get("data"))

            if data_venda is None or data_venda.date() < inicio_mes:
                continue

            forma = venda.get("forma_pagamento", "DINHEIRO")
            totais_forma[forma] = totais_forma.get(forma, 0) + float(venda.get("valor_total", 0))

        self.secao_pagamentos.limpar_corpo()

        if not totais_forma:
            self.secao_pagamentos.adicionar_vazio("Nenhuma venda registrada este mês.")
            return

        maior = max(totais_forma.values())

        for forma, valor in sorted(totais_forma.items(), key=lambda item: -item[1]):

            percentual = (valor / maior * 100) if maior else 0

            linha = LinhaProgresso(
                NOMES_FORMA_PAGAMENTO.get(forma, forma),
                None,
                _formatar_moeda(valor),
                percentual,
                CORES_FORMA_PAGAMENTO.get(forma, tokens.PRIMARIA),
            )
            self.secao_pagamentos.corpo.addWidget(linha)

    def _atualizar_top_produtos(self, vendas_finalizadas, produtos_por_id):

        hoje = datetime.now().date()
        limite = hoje - timedelta(days=30)

        qtd_por_produto = {}

        for venda in vendas_finalizadas:

            data_venda = _parse_data(venda.get("data"))

            if data_venda is None or data_venda.date() < limite:
                continue

            for item in venda.get("itens", []):
                pid = item.get("produto_id")
                qtd_por_produto[pid] = qtd_por_produto.get(pid, 0) + item.get("quantidade", 0)

        self.secao_top_produtos.limpar_corpo()

        top_produtos = sorted(qtd_por_produto.items(), key=lambda item: -item[1])[:5]

        if not top_produtos:
            self.secao_top_produtos.adicionar_vazio("Sem vendas nos últimos 30 dias.")
            return

        maior_qtd = top_produtos[0][1]

        for pid, qtd in top_produtos:

            produto = produtos_por_id.get(pid)
            nome = produto.get("nome") if produto else f"Produto #{pid}"
            percentual = (qtd / maior_qtd * 100) if maior_qtd else 0

            linha = LinhaProgresso(
                nome,
                "vendidos nos últimos 30 dias",
                f"{qtd} un.",
                percentual,
                tokens.PRIMARIA,
            )
            self.secao_top_produtos.corpo.addWidget(linha)

    def _atualizar_vendas_recentes(self, vendas_finalizadas):

        self.secao_vendas_recentes.limpar_corpo()

        recentes = sorted(
            vendas_finalizadas,
            key=lambda v: v.get("data") or "",
            reverse=True,
        )[:6]

        if not recentes:
            self.secao_vendas_recentes.adicionar_vazio("Nenhuma venda registrada ainda.")
            return

        for venda in recentes:
            data_venda = _parse_data(venda.get("data"))
            hora_texto = data_venda.strftime("%d/%m %H:%M") if data_venda else "—"
            self.secao_vendas_recentes.corpo.addWidget(
                self._linha_venda_recente(venda, hora_texto)
            )

    def _atualizar_alertas(self, produtos, contas_pagar):

        self.secao_alertas.limpar_corpo()

        hoje = datetime.now().date()

        criticos = [
            p for p in produtos
            if p.get("ativo", True) and p.get("estoque", 0) <= p.get("estoque_minimo", 0)
        ][:3]

        pendentes = sorted(
            [c for c in contas_pagar if c.get("status") == "PENDENTE"],
            key=lambda c: c.get("data_vencimento") or "",
        )[:3]

        if not criticos and not pendentes:
            self.secao_alertas.adicionar_vazio("Nenhum alerta no momento. Tudo em ordem!")
            return

        for produto in criticos:

            self.secao_alertas.corpo.addWidget(
                self._linha_alerta(
                    f"Estoque baixo: {produto.get('nome')}",
                    f"{produto.get('estoque')} un. (mínimo {produto.get('estoque_minimo')})",
                    "erro" if produto.get("estoque", 0) == 0 else "alerta",
                )
            )

        for conta in pendentes:

            vencimento = _parse_data(conta.get("data_vencimento"))
            dias = (vencimento.date() - hoje).days if vencimento else None

            if dias is None:
                texto_prazo = "sem data de vencimento"
            elif dias < 0:
                texto_prazo = f"vencida há {abs(dias)} dia(s)"
            elif dias == 0:
                texto_prazo = "vence hoje"
            else:
                texto_prazo = f"vence em {dias} dia(s)"

            self.secao_alertas.corpo.addWidget(
                self._linha_alerta(
                    conta.get("descricao") or "Conta a pagar",
                    f"{_formatar_moeda(conta.get('valor', 0))} — {texto_prazo}",
                    "erro" if (dias is not None and dias < 0) else "alerta",
                )
            )

    # ======================================
    # LINHAS AUXILIARES
    # ======================================

    def _linha_venda_recente(self, venda, hora_texto):

        linha = QFrame()
        linha.setStyleSheet("background:transparent; border:none;")

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(2)

        lbl_hora = QLabel(hora_texto)
        lbl_hora.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)

        forma = venda.get("forma_pagamento", "")
        badge_forma = Badge(
            NOMES_FORMA_PAGAMENTO.get(forma, forma),
            VARIANTE_BADGE_FORMA.get(forma, "neutro"),
        )

        col_texto.addWidget(lbl_hora)
        col_texto.addWidget(badge_forma, 0, Qt.AlignLeft)

        layout.addLayout(col_texto)
        layout.addStretch()

        lbl_valor = QLabel(_formatar_moeda(venda.get("valor_total", 0)))
        lbl_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)
        layout.addWidget(lbl_valor)

        return linha

    def _linha_alerta(self, titulo, subtitulo, variante):

        linha = QFrame()
        linha.setStyleSheet("background:transparent; border:none;")

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        cor = tokens.ERRO if variante == "erro" else tokens.ALERTA

        marcador = QFrame()
        marcador.setFixedWidth(4)
        marcador.setStyleSheet(f"background:{cor}; border-radius:2px;")

        col_texto = QVBoxLayout()
        col_texto.setSpacing(1)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setWordWrap(True)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)

        lbl_sub = QLabel(subtitulo)
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_texto.addWidget(lbl_titulo)
        col_texto.addWidget(lbl_sub)

        layout.addWidget(marcador)
        layout.addLayout(col_texto, stretch=1)

        return linha
