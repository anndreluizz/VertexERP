from datetime import datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QLinearGradient, QPainterPath
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from services.api import configuracoes
from services.venda_service import listar_vendas
from services.produto_service import listar_produtos
from services.conta_pagar_service import listar_contas_pagar
from services.caixa_service import listar_movimentacoes

from telas.relatorios import (
    PainelSecao,
    LinhaBarra,
    NOMES_FORMA_PAGAMENTO,
)


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


class GraficoDesempenho(QWidget):
    """Grafico de area simples desenhado a mao (QPainter) — sem
    depender do modulo QtCharts, pra nao arriscar mais um componente
    novo pra empacotar depois de tudo que ja deu trabalho no launcher."""

    def __init__(self):
        super().__init__()

        self.setMinimumHeight(220)
        self.pontos = []
        self.rotulos = []

    def definir_dados(self, rotulos, valores):

        self.rotulos = rotulos
        self.pontos = valores

        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        largura = self.width()
        altura = self.height()

        margem_esq = 60
        margem_dir = 20
        margem_topo = 16
        margem_baixo = 30

        area_largura = largura - margem_esq - margem_dir
        area_altura = altura - margem_topo - margem_baixo

        maior_valor = max(self.pontos) if self.pontos else 0

        if maior_valor <= 0:
            maior_valor = 1

        # linhas de grade horizontais
        pen_grade = QPen(QColor("#eeeeee"))
        pen_grade.setWidth(1)
        painter.setPen(pen_grade)

        for i in range(5):
            y = margem_topo + area_altura * i / 4
            painter.drawLine(margem_esq, int(y), largura - margem_dir, int(y))

            valor_linha = maior_valor * (4 - i) / 4
            painter.setPen(QColor("#9e9e9e"))
            painter.drawText(
                0, int(y) - 8, margem_esq - 8, 16,
                Qt.AlignRight | Qt.AlignVCenter,
                f"R${valor_linha:,.0f}".replace(",", "."),
            )
            painter.setPen(pen_grade)

        if not self.pontos or len(self.pontos) < 2:
            painter.end()
            return

        n = len(self.pontos)
        passo_x = area_largura / (n - 1)

        def coord(i, valor):
            x = margem_esq + i * passo_x
            y = margem_topo + area_altura * (
                1 - (valor / maior_valor)
            )
            return x, y

        caminho_area = QPainterPath()
        caminho_linha = QPainterPath()

        for i, valor in enumerate(self.pontos):

            x, y = coord(i, valor)

            if i == 0:
                caminho_area.moveTo(x, margem_topo + area_altura)
                caminho_area.lineTo(x, y)
                caminho_linha.moveTo(x, y)
            else:
                caminho_area.lineTo(x, y)
                caminho_linha.lineTo(x, y)

        ultimo_x, _ = coord(n - 1, self.pontos[-1])
        caminho_area.lineTo(ultimo_x, margem_topo + area_altura)
        caminho_area.closeSubpath()

        gradiente = QLinearGradient(0, margem_topo, 0, altura - margem_baixo)
        gradiente.setColorAt(0, QColor(46, 125, 50, 90))
        gradiente.setColorAt(1, QColor(46, 125, 50, 0))

        painter.fillPath(caminho_area, gradiente)

        pen_linha = QPen(QColor("#2E7D32"))
        pen_linha.setWidth(2)
        painter.setPen(pen_linha)
        painter.drawPath(caminho_linha)

        # eixo X (rotulos)
        painter.setPen(QColor("#9e9e9e"))

        passo_rotulo = max(1, n // 8)

        for i, rotulo in enumerate(self.rotulos):
            if i % passo_rotulo != 0 and i != n - 1:
                continue
            x, _ = coord(i, self.pontos[i])
            painter.drawText(
                int(x) - 20, altura - margem_baixo + 6, 40, 18,
                Qt.AlignCenter,
                rotulo,
            )

        painter.end()


class CardMetrica(QFrame):

    def __init__(self, titulo):

        super().__init__()

        self.setStyleSheet("QFrame { background:transparent; border:none; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            "background:transparent; border:none; font-size:11px; "
            "font-weight:bold; color:#9E9E9E; letter-spacing:1px;"
        )

        self.lbl_valor = QLabel("R$ 0,00")
        self.lbl_valor.setStyleSheet(
            "background:transparent; border:none; font-size:22px; "
            "font-weight:bold; color:white;"
        )

        self.lbl_variacao = QLabel("")
        self.lbl_variacao.setStyleSheet(
            "background:transparent; border:none; font-size:11px; "
            "font-weight:bold;"
        )

        layout.addWidget(lbl_titulo)
        layout.addWidget(self.lbl_valor)
        layout.addWidget(self.lbl_variacao)

    def atualizar(self, valor_texto, variacao_percentual=None):

        self.lbl_valor.setText(valor_texto)

        if variacao_percentual is None:
            self.lbl_variacao.setText("")
            return

        seta = "↑" if variacao_percentual >= 0 else "↓"
        cor = "#66BB6A" if variacao_percentual >= 0 else "#EF5350"

        self.lbl_variacao.setStyleSheet(
            f"background:transparent; border:none; font-size:11px; "
            f"font-weight:bold; color:{cor};"
        )
        self.lbl_variacao.setText(
            f"{seta} {abs(variacao_percentual):.1f}%"
        )


class VisaoGeral(QWidget):

    voltar = Signal()

    PERIODOS = [
        "Hoje",
        "Ontem",
        "Últimos 7 dias",
        "Este mês",
        "Mês anterior",
    ]

    def __init__(self):
        super().__init__()

        self.vendas = []
        self.produtos = []
        self.contas_pagar = []
        self.movimentos_caixa = []
        self.filtro_periodo = "Hoje"

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:#f4f5f7;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()

        self.bt_voltar = QPushButton("← Voltar")
        self.bt_voltar.setStyleSheet("""
            QPushButton {
                background:transparent;
                color:gray;
                border:none;
                font-size:13px;
            }
            QPushButton:hover {
                color:#202225;
            }
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        config = configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"

        titulo = QLabel(nome_loja)
        titulo.setStyleSheet(
            "background:transparent; font-size:20px; "
            "font-weight:bold; color:#202225;"
        )

        subtitulo = QLabel("LOJA OPERACIONAL")
        subtitulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "color:#2E7D32; font-weight:bold;"
        )

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addSpacing(12)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()

        bt_atualizar = QPushButton("🔄")
        bt_atualizar.setFixedSize(38, 38)
        bt_atualizar.setCursor(Qt.PointingHandCursor)
        bt_atualizar.setStyleSheet("""
            QPushButton {
                background:white;
                color:#202225;
                border:1px solid #dcdcdc;
                border-radius:8px;
                font-size:16px;
            }
            QPushButton:hover {
                border:1px solid #9e9e9e;
            }
        """)
        bt_atualizar.clicked.connect(self.carregar)

        bt_imprimir = QPushButton("🖨  Imprimir BI")
        bt_imprimir.setStyleSheet("""
            QPushButton {
                background:#202225;
                color:white;
                border-radius:8px;
                padding:10px 16px;
                font-weight:bold;
            }
            QPushButton:hover {
                background:#000000;
            }
        """)

        cabecalho.addWidget(bt_atualizar)
        cabecalho.addSpacing(8)
        cabecalho.addWidget(bt_imprimir)

        layout.addLayout(cabecalho)

        # ======================
        # FILTRO DE PERÍODO
        # ======================

        filtro_layout = QHBoxLayout()
        filtro_layout.setSpacing(8)

        self.botoes_periodo = {}

        for periodo in self.PERIODOS:

            botao = QPushButton(periodo.upper())
            botao.setCheckable(True)
            botao.setCursor(Qt.PointingHandCursor)
            botao.setMinimumHeight(34)
            botao.setStyleSheet("""
                QPushButton {
                    background:white;
                    color:#616161;
                    border:1px solid #dcdcdc;
                    border-radius:17px;
                    padding:0 16px;
                    font-size:11px;
                    font-weight:bold;
                }
                QPushButton:checked {
                    background:#2E7D32;
                    color:white;
                    border:1px solid #2E7D32;
                }
            """)
            botao.clicked.connect(
                lambda _checked, p=periodo: self._selecionar_periodo(p)
            )

            self.botoes_periodo[periodo] = botao
            filtro_layout.addWidget(botao)

        filtro_layout.addStretch()

        layout.addLayout(filtro_layout)

        self.botoes_periodo["Hoje"].setChecked(True)

        # ======================
        # BARRA ESCURA DE MÉTRICAS
        # ======================

        barra_metricas = QFrame()
        barra_metricas.setStyleSheet("""
            QFrame {
                background:#12151a;
                border-radius:12px;
            }
        """)

        metricas_layout = QHBoxLayout(barra_metricas)
        metricas_layout.setContentsMargins(24, 18, 24, 18)
        metricas_layout.setSpacing(40)

        self.card_faturamento = CardMetrica("FATURAMENTO TOTAL")
        self.card_lucro = CardMetrica("LUCRO LÍQUIDO (EST.)")
        self.card_despesas = CardMetrica("DESPESAS / SAÍDAS")
        self.card_ticket = CardMetrica("TICKET MÉDIO")

        metricas_layout.addWidget(self.card_faturamento)
        metricas_layout.addWidget(self.card_lucro)
        metricas_layout.addWidget(self.card_despesas)
        metricas_layout.addWidget(self.card_ticket)
        metricas_layout.addStretch()

        layout.addWidget(barra_metricas)

        # ======================
        # GRÁFICO DE DESEMPENHO
        # ======================

        self.painel_grafico = PainelSecao(
            "📈", "Desempenho de Vendas"
        )
        self.grafico = GraficoDesempenho()
        self.painel_grafico.corpo.addWidget(self.grafico)

        layout.addWidget(self.painel_grafico)

        # ======================
        # ÚLTIMAS TRANSAÇÕES
        # ======================

        self.painel_transacoes = PainelSecao(
            "🛒", "Últimas Transações"
        )

        self.tabela_transacoes = QTableWidget()
        self.tabela_transacoes.setColumnCount(4)
        self.tabela_transacoes.setHorizontalHeaderLabels([
            "Hora", "ID Venda", "Pagamento", "Total Bruto",
        ])
        self.tabela_transacoes.verticalHeader().setDefaultSectionSize(40)
        self.tabela_transacoes.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela_transacoes.setSelectionMode(QTableWidget.NoSelection)
        self.tabela_transacoes.setEditTriggers(
            QTableWidget.NoEditTriggers
        )
        self.tabela_transacoes.verticalHeader().setVisible(False)
        self.tabela_transacoes.setShowGrid(False)
        self.tabela_transacoes.setFocusPolicy(Qt.NoFocus)
        self.tabela_transacoes.setMinimumHeight(320)
        self.tabela_transacoes.setMaximumHeight(320)
        self.tabela_transacoes.setStyleSheet("""
            QTableWidget {
                border:none;
                color:#202225;
                background:white;
            }
            QHeaderView::section {
                background:white;
                color:#9E9E9E;
                font-weight:bold;
                font-size:11px;
                padding:6px;
                border:none;
                border-bottom:1px solid #eeeeee;
            }
        """)

        self.painel_transacoes.corpo.addWidget(self.tabela_transacoes)

        self.lbl_transacoes_vazio = QLabel(
            "Nenhuma venda registrada no período selecionado."
        )
        self.lbl_transacoes_vazio.setAlignment(Qt.AlignCenter)
        self.lbl_transacoes_vazio.setStyleSheet(
            "color:#9E9E9E; font-size:12px; background:transparent; "
            "border:none; padding:20px;"
        )
        self.lbl_transacoes_vazio.setVisible(False)
        self.painel_transacoes.corpo.addWidget(self.lbl_transacoes_vazio)

        layout.addWidget(self.painel_transacoes)

        # ======================
        # TOP PRODUTOS + MAPA DE HORÁRIOS
        # ======================

        linha_inferior = QHBoxLayout()
        linha_inferior.setSpacing(16)

        self.painel_top_produtos = PainelSecao(
            "🛒", "Top Produtos (Mais Vendidos)"
        )
        self.painel_mapa_horarios = PainelSecao(
            "🕐", "Mapa de Horários"
        )

        linha_inferior.addWidget(self.painel_top_produtos, stretch=1)
        linha_inferior.addWidget(self.painel_mapa_horarios, stretch=1)

        layout.addLayout(linha_inferior)
        layout.addStretch()

    # ==========================================
    # PERÍODO
    # ==========================================

    def _selecionar_periodo(self, periodo):

        self.filtro_periodo = periodo

        for nome, botao in self.botoes_periodo.items():
            botao.setChecked(nome == periodo)

        self._atualizar_tudo()

    def _limites_periodo(self, periodo, hoje):

        if periodo == "Hoje":
            return hoje, hoje
        if periodo == "Ontem":
            d = hoje - timedelta(days=1)
            return d, d
        if periodo == "Últimos 7 dias":
            return hoje - timedelta(days=6), hoje
        if periodo == "Este mês":
            return hoje.replace(day=1), hoje
        if periodo == "Mês anterior":
            fim = hoje.replace(day=1) - timedelta(days=1)
            return fim.replace(day=1), fim

        return hoje, hoje

    def _periodo_anterior_equivalente(self, inicio, fim):

        duracao = (fim - inicio).days + 1

        fim_anterior = inicio - timedelta(days=1)
        inicio_anterior = fim_anterior - timedelta(days=duracao - 1)

        return inicio_anterior, fim_anterior

    def _vendas_no_periodo(self, inicio, fim):

        resultado = []

        for venda in self.vendas:

            if venda.get("status") == "CANCELADA":
                continue

            data = _parse_data(venda.get("data", ""))

            if data is None:
                continue

            if inicio <= data.date() <= fim:
                resultado.append(venda)

        return resultado

    def _despesas_no_periodo(self, inicio, fim):

        total = 0.0

        for conta in self.contas_pagar:

            if conta.get("status") != "PAGO":
                continue

            data_pagamento = _parse_data(conta.get("data_pagamento", ""))

            if data_pagamento is None:
                continue

            if inicio <= data_pagamento.date() <= fim:
                total += float(conta.get("valor", 0))

        for movimento in self.movimentos_caixa:

            if movimento.get("tipo") != "SANGRIA":
                continue

            data = _parse_data(movimento.get("data", ""))

            if data is None:
                continue

            if inicio <= data.date() <= fim:
                total += abs(float(movimento.get("valor", 0)))

        return total

    def _custo_produtos_vendidos(self, vendas_periodo):

        custos_por_produto = {
            p["id"]: float(p.get("preco_custo", 0) or 0)
            for p in self.produtos
        }

        total = 0.0

        for venda in vendas_periodo:
            for item in venda.get("itens", []):
                custo_unit = custos_por_produto.get(
                    item.get("produto_id"), 0
                )
                total += custo_unit * item.get("quantidade", 0)

        return total

    # ==========================================
    # CARREGAMENTO
    # ==========================================

    def carregar(self):

        self.vendas = listar_vendas()
        self.produtos = listar_produtos()
        self.contas_pagar = listar_contas_pagar()
        self.movimentos_caixa = listar_movimentacoes()

        self._atualizar_tudo()

    def _atualizar_tudo(self):

        hoje = datetime.now().date()
        inicio, fim = self._limites_periodo(self.filtro_periodo, hoje)
        inicio_ant, fim_ant = self._periodo_anterior_equivalente(
            inicio, fim
        )

        vendas_periodo = self._vendas_no_periodo(inicio, fim)
        vendas_periodo_ant = self._vendas_no_periodo(inicio_ant, fim_ant)

        faturamento = sum(
            float(v.get("valor_total", 0)) for v in vendas_periodo
        )
        faturamento_ant = sum(
            float(v.get("valor_total", 0)) for v in vendas_periodo_ant
        )

        volume = len(vendas_periodo)
        ticket_medio = faturamento / volume if volume else 0

        volume_ant = len(vendas_periodo_ant)
        ticket_medio_ant = (
            faturamento_ant / volume_ant if volume_ant else 0
        )

        despesas = self._despesas_no_periodo(inicio, fim)
        despesas_ant = self._despesas_no_periodo(inicio_ant, fim_ant)

        custo_produtos = self._custo_produtos_vendidos(vendas_periodo)
        custo_produtos_ant = self._custo_produtos_vendidos(
            vendas_periodo_ant
        )

        lucro = faturamento - custo_produtos - despesas
        lucro_ant = faturamento_ant - custo_produtos_ant - despesas_ant

        def variacao(atual, anterior):
            if anterior == 0:
                return None if atual == 0 else 100.0
            return ((atual - anterior) / anterior) * 100

        self.card_faturamento.atualizar(
            _formatar_moeda(faturamento),
            variacao(faturamento, faturamento_ant),
        )
        self.card_lucro.atualizar(
            _formatar_moeda(lucro),
            variacao(lucro, lucro_ant),
        )
        self.card_despesas.atualizar(
            _formatar_moeda(despesas),
            variacao(despesas, despesas_ant),
        )
        self.card_ticket.atualizar(
            _formatar_moeda(ticket_medio),
            variacao(ticket_medio, ticket_medio_ant),
        )

        self._atualizar_grafico(vendas_periodo, inicio, fim)
        self._atualizar_transacoes(vendas_periodo)
        self._atualizar_top_produtos(vendas_periodo)
        self._atualizar_mapa_horarios(vendas_periodo)

    def _atualizar_grafico(self, vendas_periodo, inicio, fim):

        dias_no_periodo = (fim - inicio).days + 1

        if dias_no_periodo <= 1:

            totais = [0.0] * 24

            for venda in vendas_periodo:
                data = _parse_data(venda.get("data", ""))
                if data:
                    totais[data.hour] += float(
                        venda.get("valor_total", 0)
                    )

            rotulos = [f"{h:02d}h" for h in range(24)]

        else:

            totais_por_dia = {}
            dia = inicio

            while dia <= fim:
                totais_por_dia[dia] = 0.0
                dia += timedelta(days=1)

            for venda in vendas_periodo:
                data = _parse_data(venda.get("data", ""))
                if data and data.date() in totais_por_dia:
                    totais_por_dia[data.date()] += float(
                        venda.get("valor_total", 0)
                    )

            rotulos = [
                d.strftime("%d/%m") for d in totais_por_dia
            ]
            totais = list(totais_por_dia.values())

        self.grafico.definir_dados(rotulos, totais)

    def _atualizar_transacoes(self, vendas_periodo):

        vendas_ordenadas = sorted(
            vendas_periodo,
            key=lambda v: v.get("data", ""),
            reverse=True,
        )[:10]

        self.tabela_transacoes.setRowCount(0)

        for venda in vendas_ordenadas:

            linha = self.tabela_transacoes.rowCount()
            self.tabela_transacoes.insertRow(linha)

            data = _parse_data(venda.get("data", ""))
            hora_texto = data.strftime("%H:%M") if data else "—"

            forma = venda.get("forma_pagamento", "DINHEIRO")
            forma_texto = NOMES_FORMA_PAGAMENTO.get(forma, forma)

            forma_2 = venda.get("forma_pagamento_2")
            if forma_2:
                forma_texto += (
                    f" + {NOMES_FORMA_PAGAMENTO.get(forma_2, forma_2)}"
                )

            self.tabela_transacoes.setItem(
                linha, 0, QTableWidgetItem(hora_texto)
            )
            self.tabela_transacoes.setItem(
                linha, 1, QTableWidgetItem(f"#{venda.get('id')}")
            )
            self.tabela_transacoes.setItem(
                linha, 2, QTableWidgetItem(forma_texto)
            )
            self.tabela_transacoes.setItem(
                linha, 3,
                QTableWidgetItem(
                    _formatar_moeda(venda.get("valor_total", 0))
                ),
            )

        self.tabela_transacoes.setVisible(bool(vendas_ordenadas))
        self.lbl_transacoes_vazio.setVisible(not vendas_ordenadas)

    def _atualizar_top_produtos(self, vendas_periodo):

        self.painel_top_produtos.limpar_corpo()

        nomes_produto = {p["id"]: p["nome"] for p in self.produtos}

        totais_por_produto = {}

        for venda in vendas_periodo:
            for item in venda.get("itens", []):
                produto_id = item.get("produto_id")
                totais_por_produto[produto_id] = (
                    totais_por_produto.get(produto_id, 0)
                    + item.get("quantidade", 0)
                )

        if not totais_por_produto:
            self.painel_top_produtos.adicionar_vazio(
                "Nenhuma venda no período selecionado."
            )
            return

        ranking = sorted(
            totais_por_produto.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:5]

        maior_qtd = ranking[0][1] if ranking else 1

        for produto_id, quantidade in ranking:

            nome = nomes_produto.get(produto_id, "Produto removido")
            percentual = (quantidade / maior_qtd) * 100

            linha = LinhaBarra(
                nome,
                None,
                f"{quantidade} vendas",
                percentual,
                "#1565C0",
            )

            self.painel_top_produtos.corpo.addWidget(linha)

    def _atualizar_mapa_horarios(self, vendas_periodo):

        self.painel_mapa_horarios.limpar_corpo()

        if not vendas_periodo:
            self.painel_mapa_horarios.adicionar_vazio(
                "Nenhuma venda no período selecionado."
            )
            return

        contagem = {"Manhã (06h-12h)": 0, "Tarde (12h-18h)": 0, "Noite (18h-24h)": 0}

        for venda in vendas_periodo:

            data = _parse_data(venda.get("data", ""))

            if not data:
                continue

            if 6 <= data.hour < 12:
                contagem["Manhã (06h-12h)"] += 1
            elif 12 <= data.hour < 18:
                contagem["Tarde (12h-18h)"] += 1
            else:
                contagem["Noite (18h-24h)"] += 1

        total = sum(contagem.values()) or 1

        for rotulo, quantidade in contagem.items():

            percentual = (quantidade / total) * 100

            linha = LinhaBarra(
                rotulo,
                None,
                f"{percentual:.0f}%",
                percentual,
                "#F9A825",
            )

            self.painel_mapa_horarios.corpo.addWidget(linha)
