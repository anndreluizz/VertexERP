from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
)

from services import comprovante_service
from services.api import configuracoes
from services.relatorio_service import (
    relatorio_vendas,
    funil_vendas,
    comparativo_lojas,
)
from services.worker import rodar_em_thread
from design import tokens
from design.charts import GraficoArea, GraficoPizza
from design.widgets import CardKPI
from utils.formatacao import formatar_moeda
from utils.documento_html import (
    ESTILO_BODY,
    bloco_total,
    cabecalho_html,
    cabecalho_tabela,
    linha_zebra,
    rodape_nao_fiscal,
)
from widgets.dialogs.message_dialog import Mensagem
from telas.relatorios.comum import (
    CORES_FORMA_PAGAMENTO,
    NOMES_FORMA_PAGAMENTO,
    _listar_lojas_para_combo,
)
from telas.relatorios.widgets import LinhaBarra, PainelSecao


class FinanceiroMixin:
    """Aba Financeiro: periodo, lojas, funil, tendencia, ranking, mix de pagamentos e impressao."""

    # ==========================================
    # PÁGINA: CENTRO FINANCEIRO
    # ==========================================

    def _criar_pagina_financeiro(self):

        pagina, layout = self._pagina_rolavel()

        filtro_layout = QHBoxLayout()

        self.combo_periodo = QComboBox()
        self.combo_periodo.addItems(self.PERIODOS)
        self.combo_periodo.setCurrentText("Este mês")
        self.combo_periodo.setMinimumHeight(38)
        self.combo_periodo.setCursor(Qt.PointingHandCursor)
        self.combo_periodo.setStyleSheet(f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:4px 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """)
        # debounced: cada mudanca de periodo dispara uma chamada de
        # rede pro backend (agregado agora, nao mais um filtro local)
        # -- sem isso, alguem clicando rapido por varias opcoes do
        # combo dispararia uma requisicao sincrona bloqueante por
        # clique. Reiniciar o timer a cada mudanca faz so a ultima
        # selecao "vencer".
        self._timer_atualizar_financeiro = QTimer(self)
        self._timer_atualizar_financeiro.setSingleShot(True)
        self._timer_atualizar_financeiro.timeout.connect(
            self._atualizar_financeiro
        )
        self.combo_periodo.currentTextChanged.connect(
            lambda: self._timer_atualizar_financeiro.start(300)
        )

        self.combo_loja = QComboBox()
        self.combo_loja.setMinimumHeight(38)
        self.combo_loja.setCursor(Qt.PointingHandCursor)
        self.combo_loja.setStyleSheet(f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:4px 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """)
        self._carregar_combo_lojas(self.combo_loja)
        self.combo_loja.currentIndexChanged.connect(
            lambda: self._timer_atualizar_financeiro.start(300)
        )

        filtro_layout.addWidget(self.combo_periodo)
        filtro_layout.addWidget(self.combo_loja)
        filtro_layout.addStretch()

        layout.addLayout(filtro_layout)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)

        self.card_faturamento = CardKPI(
            "Faturamento Bruto", "dollar-sign", tokens.PRIMARIA, destaque=True
        )
        self.card_lucro = CardKPI("Lucro", "trending-up", tokens.SECUNDARIA)
        self.card_volume = CardKPI("Vendas", "shopping-cart", tokens.PRIMARIA)
        self.card_ticket = CardKPI("Ticket Médio", "bar-chart-2", tokens.ALERTA)

        for card in (self.card_faturamento, self.card_lucro, self.card_volume, self.card_ticket):
            cards_layout.addWidget(card, 1)

        layout.addLayout(cards_layout)

        painel_tendencia = PainelSecao("📈", "Faturamento no Período")
        self.grafico_tendencia = GraficoArea()
        painel_tendencia.corpo.addWidget(self.grafico_tendencia)
        layout.addWidget(painel_tendencia)

        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(16)

        self.painel_ranking = PainelSecao("📦", "Ranking de Produtos")
        self.painel_mix = PainelSecao("💳", "Mix de Pagamentos")

        self.grafico_mix = GraficoPizza()
        self.grafico_mix.setFixedHeight(140)
        # entra entre o cabecalho do painel e o corpo (lista de
        # LinhaBarra) -- fora de self.painel_mix.corpo de proposito,
        # pra nao ser apagado toda vez que _atualizar_mix_pagamentos
        # chama limpar_corpo()
        self.painel_mix.layout_externo.insertWidget(1, self.grafico_mix)

        grid_layout.addWidget(self.painel_ranking, stretch=1)
        grid_layout.addWidget(self.painel_mix, stretch=1)

        layout.addLayout(grid_layout)

        self.painel_funil = PainelSecao("🔻", "Funil de Vendas")

        subtitulo_funil = QLabel(
            "Carrinhos em aberto é uma contagem ao vivo (agora), sem "
            "recorte de período — rascunhos excluídos não deixam "
            "rastro. Finalizadas/canceladas são do período selecionado "
            "acima."
        )
        subtitulo_funil.setWordWrap(True)
        subtitulo_funil.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; border:none;"
        )
        # fora de self.painel_funil.corpo de proposito -- mesmo motivo
        # do self.grafico_mix acima, corpo e' limpo a cada refresh
        self.painel_funil.layout_externo.insertWidget(1, subtitulo_funil)

        layout.addWidget(self.painel_funil)

        self.painel_comparativo_lojas = PainelSecao("🏬", "Comparativo entre Lojas")

        self.tabela_comparativo_lojas = QTableWidget()
        self.tabela_comparativo_lojas.setColumnCount(5)
        self.tabela_comparativo_lojas.setHorizontalHeaderLabels(
            ["Loja", "Faturamento", "Lucro", "Qtd. Vendas", "Ticket Médio"]
        )
        self._estilizar_tabela(self.tabela_comparativo_lojas)
        self.tabela_comparativo_lojas.setMinimumHeight(150)
        self.painel_comparativo_lojas.corpo.addWidget(self.tabela_comparativo_lojas)

        layout.addWidget(self.painel_comparativo_lojas)
        layout.addStretch()

        return pagina

    def _periodo_selecionado(self):
        """Traduz a opção escolhida no combo pra um intervalo (inicio,
        fim) de datas -- mesmos limites de sempre, só que agora servem
        pra montar a query do relatório agregado no backend em vez de
        filtrar uma lista de vendas já em memória."""

        return self._calcular_periodo(self.combo_periodo)

    def _calcular_periodo(self, combo):
        """Mesma logica de _periodo_selecionado, parametrizada pelo
        combo -- usado tambem pelo combo de periodo da Curva ABC, que
        e' independente do combo do Centro Financeiro."""

        periodo = combo.currentText()
        hoje = datetime.now().date()

        if periodo == "Hoje":
            return hoje, hoje

        if periodo == "Ontem":
            ontem = hoje - timedelta(days=1)
            return ontem, ontem

        if periodo == "Últimos 7 dias":
            return hoje - timedelta(days=6), hoje

        if periodo == "Este mês":
            return hoje.replace(day=1), hoje

        if periodo == "Mês anterior":
            primeiro_dia_mes_atual = hoje.replace(day=1)
            fim = primeiro_dia_mes_atual - timedelta(days=1)
            return fim.replace(day=1), fim

        # "Tudo" -- inicio=None diz pro backend pra não aplicar limite
        # inferior nenhum, em vez de fingir isso com uma data hardcoded
        # (que descartaria vendas reais anteriores a ela e ainda
        # forçaria um cálculo de "período anterior" sem sentido pra
        # comparação -- ver RelatorioService.vendas_geral).
        return None, hoje

    def _carregar_combo_lojas(self, combo):

        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Todas as lojas", None)
        combo.blockSignals(False)

        rodar_em_thread(
            self,
            _listar_lojas_para_combo,
            combo,
            ao_sucesso=self._ao_carregar_combo_lojas_sucesso,
        )

    def _ao_carregar_combo_lojas_sucesso(self, resultado):

        lojas, combo = resultado

        combo.blockSignals(True)

        for loja in lojas:
            combo.addItem(loja["nome"], loja["id"])

        combo.blockSignals(False)

    def _atualizar_financeiro(self):

        if self._carregando_financeiro:
            return
        self._carregando_financeiro = True

        inicio, fim = self._periodo_selecionado()

        rodar_em_thread(
            self,
            relatorio_vendas,
            inicio.isoformat() if inicio else None,
            fim.isoformat(),
            limit=1,
            top_produtos_limite=10,
            top_produtos_ordenar_por="valor",
            loja_id=self.combo_loja.currentData(),
            ao_sucesso=self._ao_atualizar_financeiro_sucesso,
            ao_erro=self._ao_atualizar_financeiro_erro,
            ao_finalizar=self._ao_atualizar_financeiro_finalizado,
        )

        # comparativo entre lojas sempre mostra todas as lojas
        # (independe do filtro self.combo_loja) -- chamada paralela,
        # nao depende do resultado de relatorio_vendas acima
        rodar_em_thread(
            self,
            comparativo_lojas,
            inicio.isoformat() if inicio else None,
            fim.isoformat(),
            ao_sucesso=self._ao_atualizar_comparativo_lojas_sucesso,
            ao_erro=self._ao_atualizar_secao_secundaria_erro,
        )

        rodar_em_thread(
            self,
            funil_vendas,
            inicio.isoformat() if inicio else None,
            fim.isoformat(),
            ao_sucesso=self._ao_atualizar_funil_sucesso,
            ao_erro=self._ao_atualizar_secao_secundaria_erro,
        )

    def _ao_atualizar_funil_sucesso(self, dados):

        self.painel_funil.limpar_corpo()

        maior_valor = max(
            dados["suspensas_agora"], dados["finalizadas"], dados["canceladas"], 1
        )

        self.painel_funil.corpo.addWidget(LinhaBarra(
            "Carrinhos em aberto agora",
            None,
            str(dados["suspensas_agora"]),
            dados["suspensas_agora"] / maior_valor * 100,
            tokens.TEXTO_SECUNDARIO,
        ))
        self.painel_funil.corpo.addWidget(LinhaBarra(
            "Vendas finalizadas",
            "no período selecionado",
            str(dados["finalizadas"]),
            dados["finalizadas"] / maior_valor * 100,
            tokens.SECUNDARIA_HOVER,
        ))
        self.painel_funil.corpo.addWidget(LinhaBarra(
            "Vendas canceladas",
            f"{float(dados['taxa_cancelamento']):.1f}".replace(".", ",") + "% das vendas do período",
            str(dados["canceladas"]),
            dados["canceladas"] / maior_valor * 100,
            tokens.ERRO,
        ))

    def _ao_atualizar_comparativo_lojas_sucesso(self, itens):

        self.tabela_comparativo_lojas.setRowCount(len(itens))

        for linha, item in enumerate(itens):
            self.tabela_comparativo_lojas.setItem(
                linha, 0, QTableWidgetItem(item["loja_nome"])
            )
            self.tabela_comparativo_lojas.setItem(
                linha, 1, QTableWidgetItem(formatar_moeda(item["receita_total"]))
            )
            self.tabela_comparativo_lojas.setItem(
                linha, 2, QTableWidgetItem(
                    "—" if item.get("custo_incompleto") else formatar_moeda(item["lucro"])
                )
            )
            self.tabela_comparativo_lojas.setItem(
                linha, 3, QTableWidgetItem(str(item["quantidade_vendas"]))
            )
            self.tabela_comparativo_lojas.setItem(
                linha, 4, QTableWidgetItem(formatar_moeda(item["ticket_medio"]))
            )

    def _ao_atualizar_financeiro_erro(self, erro):
        Mensagem.erro(
            self,
            "Não foi possível carregar o relatório financeiro.\n"
            f"Os valores exibidos abaixo não refletem o período "
            f"selecionado.\n\nDetalhes: {erro}",
        )
        self.card_faturamento.definir_valor(formatar_moeda(0))
        self.card_volume.definir_valor("0")
        self.card_ticket.definir_valor(formatar_moeda(0))
        self._atualizar_ranking_produtos([])
        self._atualizar_mix_pagamentos([])
        self.grafico_tendencia.definir_dados([], [])

    def _ao_atualizar_financeiro_finalizado(self):
        self._carregando_financeiro = False

    def imprimir_relatorio_financeiro(self):

        if self._aba_atual != 0:
            return

        if not self._ultimo_relatorio_financeiro:
            Mensagem.erro(
                self, "Aguarde o relatório financeiro carregar antes de imprimir."
            )
            return

        relatorio = self._ultimo_relatorio_financeiro

        linhas_produtos = "".join(
            linha_zebra(
                [item["produto"], item["quantidade"], formatar_moeda(item["total"])],
                indice,
                alinhamentos=["left", "center", "right"],
            )
            for indice, item in enumerate(relatorio["top_produtos"])
        ) or linha_zebra(["Nenhuma venda no período.", "", ""], 0)

        linhas_pagamento = "".join(
            linha_zebra(
                [
                    NOMES_FORMA_PAGAMENTO.get(item["forma_pagamento"], item["forma_pagamento"]),
                    item["quantidade"],
                    formatar_moeda(item["total"]),
                ],
                indice,
                alinhamentos=["left", "center", "right"],
            )
            for indice, item in enumerate(relatorio["formas_pagamento"])
        ) or linha_zebra(["Nenhuma venda no período.", "", ""], 0)

        periodo_texto = self.combo_periodo.currentText()
        loja_texto = self.combo_loja.currentText()

        html = f"""
        <html>
        <body style="{ESTILO_BODY}">
            {cabecalho_html(
                "RELATÓRIO FINANCEIRO",
                configuracoes(),
                comprovante_service.obter_logo_loja(),
            )}
            <p style="margin:4px 0;">Período: {periodo_texto}</p>
            <p style="margin:4px 0;">Loja: {loja_texto}</p>
            <p style="margin:4px 0;">
                Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </p>
            <h4 style="margin:16px 0 6px; color:#1E293B;">RANKING DE PRODUTOS</h4>
            <table style="width:100%; border-collapse:collapse; border:1px solid #E5E7EB;">
                {cabecalho_tabela(
                    ["Produto", "Qtd", "Total"], ["left", "center", "right"]
                )}
                {linhas_produtos}
            </table>
            <h4 style="margin:16px 0 6px; color:#1E293B;">MIX DE PAGAMENTOS</h4>
            <table style="width:100%; border-collapse:collapse; border:1px solid #E5E7EB;">
                {cabecalho_tabela(
                    ["Forma", "Qtd", "Total"], ["left", "center", "right"]
                )}
                {linhas_pagamento}
            </table>
            {bloco_total(
                "FATURAMENTO BRUTO",
                formatar_moeda(float(relatorio["receita_total"]["atual"])),
            )}
            {rodape_nao_fiscal("Relatório interno -- não possui valor fiscal.")}
        </body>
        </html>
        """

        comprovante_service.imprimir(html, self)

    def _ao_atualizar_financeiro_sucesso(self, relatorio):

        self._ultimo_relatorio_financeiro = relatorio

        faturamento = float(relatorio["receita_total"]["atual"])
        volume = int(relatorio["quantidade_vendas"]["atual"])
        ticket_medio = float(relatorio["ticket_medio"]["atual"])
        lucro = float((relatorio.get("lucro") or {}).get("atual") or 0)
        margem = float((relatorio.get("margem_lucro") or {}).get("atual") or 0)

        self.card_faturamento.definir_valor(formatar_moeda(faturamento))
        self.card_lucro.definir_valor(formatar_moeda(lucro))
        self.card_volume.definir_valor(str(volume))
        self.card_ticket.definir_valor(formatar_moeda(ticket_medio))

        # variação contra o período anterior de mesmo tamanho (o backend
        # manda None quando não tem base -- aí o selo some)
        for card, chave in (
            (self.card_faturamento, "receita_total"), (self.card_lucro, "lucro"),
            (self.card_volume, "quantidade_vendas"), (self.card_ticket, "ticket_medio"),
        ):
            variacao = (relatorio.get(chave) or {}).get("variacao_pct")
            card.definir_variacao(variacao, "vs período anterior")
            if variacao is None:
                card.definir_legenda("sem período anterior pra comparar")

        self.card_lucro.definir_legenda(f"margem de {margem:.1f}%".replace(".", ","))
        if relatorio.get("custo_incompleto"):
            self.card_lucro.definir_valor("—")
            self.card_lucro.definir_variacao(None)
            self.card_lucro.definir_legenda("produto vendido sem custo cadastrado")

        self._atualizar_ranking_produtos(relatorio["top_produtos"])
        self._atualizar_mix_pagamentos(relatorio["formas_pagamento"])
        self._atualizar_tendencia(relatorio["vendas_por_dia"])

    def _atualizar_tendencia(self, vendas_por_dia):

        if not vendas_por_dia:
            self.grafico_tendencia.definir_dados([], [])
            return

        rotulos = []
        rotulos_completos = []
        valores = []

        totais = {item["data"]: float(item["total"]) for item in vendas_por_dia}

        # o backend só manda dia que teve venda -- sem completar com zero
        # o gráfico pulava os dias parados (e com 1 dia só nem desenhava)
        inicio, fim = self._periodo_selecionado()
        if inicio is None:
            inicio = datetime.strptime(min(totais), "%Y-%m-%d").date()
        dias = []
        if (fim - inicio).days <= 92:
            dia = inicio
            while dia <= fim:
                dias.append(dia)
                dia += timedelta(days=1)
        else:
            dias = [datetime.strptime(d, "%Y-%m-%d").date() for d in sorted(totais)]

        for dia in dias:
            rotulos.append(dia.strftime("%d/%m"))
            rotulos_completos.append(dia.strftime("%d/%m/%Y"))
            valores.append(totais.get(dia.strftime("%Y-%m-%d"), 0.0))

        self.grafico_tendencia.definir_dados(rotulos, valores, rotulos_completos)

    def _atualizar_ranking_produtos(self, top_produtos):

        self.painel_ranking.limpar_corpo()

        if not top_produtos:
            self.painel_ranking.adicionar_vazio(
                "Nenhuma venda no período selecionado."
            )
            return

        maior_valor = float(top_produtos[0]["total"]) or 1

        for posicao, item in enumerate(top_produtos, start=1):

            total = float(item["total"])

            percentual = (
                (total / maior_valor) * 100 if maior_valor else 0
            )

            linha = LinhaBarra(
                f"{posicao}. {item['produto']}",
                None,
                formatar_moeda(total),
                percentual,
                tokens.PRIMARIA,
            )

            self.painel_ranking.corpo.addWidget(linha)

    def _atualizar_mix_pagamentos(self, formas_pagamento):

        self.painel_mix.limpar_corpo()

        total_geral = sum(float(item["total"]) for item in formas_pagamento)

        self.grafico_mix.definir_dados([
            (
                float(item["total"]),
                CORES_FORMA_PAGAMENTO.get(item["forma_pagamento"], tokens.TEXTO),
            )
            for item in formas_pagamento
        ])

        if not total_geral:
            self.painel_mix.adicionar_vazio(
                "Nenhuma venda no período selecionado."
            )
            return

        # o backend (RelatorioService._formas_pagamento) já devolve a
        # lista ordenada do maior pro menor total
        for item in formas_pagamento:

            forma = item["forma_pagamento"]
            total = float(item["total"])
            percentual = (total / total_geral) * 100

            nome = NOMES_FORMA_PAGAMENTO.get(forma, forma)
            cor = CORES_FORMA_PAGAMENTO.get(forma, tokens.TEXTO)

            linha = LinhaBarra(
                nome,
                f"{percentual:.1f}".replace(".", ",") + "% do total",
                formatar_moeda(total),
                percentual,
                cor,
            )

            self.painel_mix.corpo.addWidget(linha)
