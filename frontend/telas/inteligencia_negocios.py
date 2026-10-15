"""Inteligencia de Negocios: mostra o /bi/resumo do backend (numeros e
recomendacoes ja calculados la, nada estimado aqui) com filtro de
periodo e loja."""

from datetime import date, datetime, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.widgets import Badge, BotaoSecundario, CardKPI, SecaoCard, pedir_texto, tabela_lista
from services.bi_service import informar_dinheiro_guardado, resumo
from services.loja_service import listar_lojas
from services.worker import rodar_em_thread
from utils.formatacao import formatar_moeda

PERIODOS = [
    "Hoje",
    "Últimos 7 dias",
    "Últimos 30 dias",
    "Mês atual",
    "Mês anterior",
    "Período personalizado",
]

PRIORIDADES = {
    "critica": ("Crítica", "erro"),
    "alta": ("Alta", "alerta"),
    "media": ("Média", "info"),
    "baixa": ("Baixa", "neutro"),
}


def datas_do_periodo(nome, hoje):
    """(inicio, fim) de cada opcao do combo; "Período personalizado"
    devolve None (as datas vem dos campos)."""
    if nome == "Hoje":
        return hoje, hoje
    if nome == "Últimos 7 dias":
        return hoje - timedelta(days=6), hoje
    if nome == "Últimos 30 dias":
        return hoje - timedelta(days=29), hoje
    if nome == "Mês atual":
        return hoje.replace(day=1), hoje
    if nome == "Mês anterior":
        fim = hoje.replace(day=1) - timedelta(days=1)
        return fim.replace(day=1), fim
    return None


def _buscar(data_inicio, data_fim, loja_id):
    """Roda na worker thread."""
    return resumo(data_inicio.isoformat(), data_fim.isoformat(), loja_id)


def valor_digitado(texto):
    """'10.000,50' / 'R$ 800' / '1500.5' -> float >= 0, ou None se invalido."""
    texto = (texto or "").replace("R$", "").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        valor = float(texto)
    except ValueError:
        return None
    return valor if valor >= 0 else None


def _texto(texto, tamanho=None, cor=None, negrito=False):
    lbl = QLabel(texto)
    lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lbl.setStyleSheet(
        f"background:transparent; color:{cor or tokens.TEXTO}; "
        f"font-size:{tamanho or tokens.TAMANHO_SM}px; "
        f"font-weight:{700 if negrito else 400};"
    )
    return lbl


def _preencher(tabela, linhas):
    tabela.setRowCount(len(linhas))
    for i, linha in enumerate(linhas):
        for j, valor in enumerate(linha):
            tabela.setItem(i, j, QTableWidgetItem(str(valor)))
    # tabela sem rolagem propria: a pagina inteira ja rola
    altura = tabela.horizontalHeader().height() + 46 * max(len(linhas), 1) + 4
    tabela.setFixedHeight(altura)


class InteligenciaNegocios(QWidget):

    def __init__(self):
        super().__init__()

        self._carregando = False
        self._lojas_carregadas = False

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        externo.addWidget(rolagem)

        conteudo = QWidget()
        rolagem.setWidget(conteudo)
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(16)

        # ---------------- filtros ----------------
        estilo_campo = f"""
            QComboBox, QDateEdit {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:4px 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
                min-height:30px;
            }}
        """
        filtros = QHBoxLayout()
        filtros.setSpacing(10)

        self.combo_periodo = QComboBox()
        self.combo_periodo.addItems(PERIODOS)
        self.combo_periodo.setCurrentText("Mês atual")
        self.combo_periodo.setStyleSheet(estilo_campo)
        self.combo_periodo.currentTextChanged.connect(self._ao_mudar_periodo)

        self.data_inicio = QDateEdit()
        self.data_fim = QDateEdit()
        for campo in (self.data_inicio, self.data_fim):
            campo.setCalendarPopup(True)
            campo.setDisplayFormat("dd/MM/yyyy")
            campo.setDate(QDate.currentDate())
            campo.setStyleSheet(estilo_campo)
            campo.setVisible(False)

        self.combo_loja = QComboBox()
        self.combo_loja.addItem("Todas as lojas", None)
        self.combo_loja.setStyleSheet(estilo_campo)

        self.bt_atualizar = BotaoSecundario("Atualizar")
        self.bt_atualizar.clicked.connect(self.carregar)

        filtros.addWidget(self.combo_periodo)
        filtros.addWidget(self.data_inicio)
        filtros.addWidget(self.data_fim)
        filtros.addWidget(self.combo_loja)
        filtros.addWidget(self.bt_atualizar)
        filtros.addStretch()
        layout.addLayout(filtros)

        self.lbl_periodo = _texto("", cor=tokens.TEXTO_SECUNDARIO)
        layout.addWidget(self.lbl_periodo)

        # cofre + banco: o sistema nao sabe pra onde vai o dinheiro quando
        # o caixa fecha, entao o dono informa (entra na previsao de 30 dias)
        linha_guardado = QHBoxLayout()
        self.lbl_guardado = _texto("", cor=tokens.TEXTO_SECUNDARIO)
        self.bt_guardado = BotaoSecundario("Conferir dinheiro guardado")
        self.bt_guardado.clicked.connect(self._informar_guardado)
        linha_guardado.addWidget(self.lbl_guardado, 1)
        linha_guardado.addWidget(self.bt_guardado)
        layout.addLayout(linha_guardado)
        self._guardado_atual = None

        self.lbl_erro = _texto("", cor=tokens.ERRO)
        self.lbl_erro.setVisible(False)
        layout.addWidget(self.lbl_erro)

        # ---------------- KPIs ----------------
        grade = QGridLayout()
        grade.setSpacing(14)
        self.card_faturamento = CardKPI("Faturamento líquido", "dollar-sign",
                                        tokens.PRIMARIA, destaque=True)
        self.card_vendas = CardKPI("Vendas", "shopping-cart", tokens.PRIMARIA)
        self.card_ticket = CardKPI("Ticket médio", "trending-up", tokens.SECUNDARIA)
        self.card_lucro = CardKPI("Lucro bruto", "bar-chart-2", tokens.SECUNDARIA)
        self.card_fiado = CardKPI("Fiado em aberto", "users", tokens.ALERTA)
        self.card_recebido = CardKPI("Fiado recebido", "wallet", tokens.SUCESSO)
        self.card_contas = CardKPI("Contas a pagar (30 dias)", "file-text", tokens.ERRO)
        self.card_previsao = CardKPI("Previsão 30 dias", "calendar", tokens.PRIMARIA)
        cards = [
            self.card_faturamento, self.card_vendas, self.card_ticket, self.card_lucro,
            self.card_fiado, self.card_recebido, self.card_contas, self.card_previsao,
        ]
        for i, card in enumerate(cards):
            grade.addWidget(card, i // 4, i % 4)
        layout.addLayout(grade)

        # ---------------- avisos e recomendacoes ----------------
        self.secao_avisos = SecaoCard("Dados incompletos", "alert-triangle")
        layout.addWidget(self.secao_avisos)

        self.secao_recomendacoes = SecaoCard("Recomendações", "lightbulb")
        layout.addWidget(self.secao_recomendacoes)

        # ---------------- tabelas ----------------
        self.secao_lojas = SecaoCard("Matriz × Filial", "store")
        self.tabela_lojas = tabela_lista([
            "Loja", "Faturamento", "Vendas", "Ticket médio", "À vista", "A prazo",
            "Fiado recebido", "Contas 30 dias", "Nos caixas abertos",
        ])
        self.secao_lojas.corpo.addWidget(self.tabela_lojas)
        layout.addWidget(self.secao_lojas)

        linha1 = QHBoxLayout()
        linha1.setSpacing(14)
        self.secao_formas = SecaoCard("Formas de pagamento", "credit-card")
        self.tabela_formas = tabela_lista(["Forma", "Vendas", "Total"])
        self.secao_formas.corpo.addWidget(self.tabela_formas)
        self.secao_contas = SecaoCard("Contas a pagar próximas", "file-text")
        self.tabela_contas = tabela_lista(["Vencimento", "Descrição", "Valor"])
        self.secao_contas.corpo.addWidget(self.tabela_contas)
        linha1.addWidget(self.secao_formas, 2, Qt.AlignTop)
        linha1.addWidget(self.secao_contas, 3, Qt.AlignTop)
        layout.addLayout(linha1)

        linha2 = QHBoxLayout()
        linha2.setSpacing(14)
        self.secao_faixas = SecaoCard("Fiado por tempo de atraso", "calendar")
        self.tabela_faixas = tabela_lista(["Atraso", "Clientes", "Total"])
        self.secao_faixas.corpo.addWidget(self.tabela_faixas)
        self.secao_devedores = SecaoCard("Maiores devedores", "users")
        self.tabela_devedores = tabela_lista(["Cliente", "Saldo", "Atraso", "Telefone"])
        self.secao_devedores.corpo.addWidget(self.tabela_devedores)
        linha2.addWidget(self.secao_faixas, 2, Qt.AlignTop)
        linha2.addWidget(self.secao_devedores, 3, Qt.AlignTop)
        layout.addLayout(linha2)

        self.secao_produtos = SecaoCard("Mais vendidos", "package")
        self.tabela_produtos = tabela_lista(["Produto", "Quantidade", "Total"])
        self.secao_produtos.corpo.addWidget(self.tabela_produtos)
        layout.addWidget(self.secao_produtos)

        layout.addStretch()

    # ---------------- carregamento ----------------

    def carregar(self):
        if not self._lojas_carregadas:
            rodar_em_thread(self, listar_lojas, ao_sucesso=self._ao_carregar_lojas)

        datas = self._datas_escolhidas()
        if datas is None or self._carregando:
            return
        self._carregando = True
        self.bt_atualizar.setEnabled(False)
        self.lbl_periodo.setText("Carregando…")
        rodar_em_thread(
            self, _buscar, *datas, self.combo_loja.currentData(),
            ao_sucesso=self._ao_carregar,
            ao_erro=self._ao_erro,
            ao_finalizar=self._ao_finalizar,
        )

    def _datas_escolhidas(self):
        datas = datas_do_periodo(self.combo_periodo.currentText(), date.today())
        if datas is not None:
            return datas
        inicio = self.data_inicio.date().toPython()
        fim = self.data_fim.date().toPython()
        if fim < inicio:
            self._mostrar_erro("A data final não pode ser antes da inicial.")
            return None
        return inicio, fim

    def _ao_mudar_periodo(self, nome):
        personalizado = nome == "Período personalizado"
        self.data_inicio.setVisible(personalizado)
        self.data_fim.setVisible(personalizado)
        if not personalizado:
            self.carregar()

    def _ao_carregar_lojas(self, lojas):
        self._lojas_carregadas = True
        for loja in lojas:
            self.combo_loja.addItem(loja["nome"], loja["id"])
        self.combo_loja.currentIndexChanged.connect(self.carregar)

    def _ao_finalizar(self):
        self._carregando = False
        self.bt_atualizar.setEnabled(True)

    def _ao_erro(self, erro):
        self._mostrar_erro(str(erro))

    def _mostrar_erro(self, texto):
        self.lbl_periodo.setText("")
        self.lbl_erro.setText(texto)
        self.lbl_erro.setVisible(True)

    def _ao_carregar(self, dados):
        self.lbl_erro.setVisible(False)
        periodo = dados["periodo"]
        inicio = date.fromisoformat(periodo["data_inicio"])
        fim = date.fromisoformat(periodo["data_fim"])
        gerado = datetime.fromisoformat(periodo["gerado_em"])
        self.lbl_periodo.setText(
            f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y} · {periodo['loja_nome']} · "
            f"dados do sistema às {gerado:%H:%M}"
        )
        self._mostrar_guardado(dados["caixa"])
        self._mostrar_kpis(dados)
        self._mostrar_avisos(dados["avisos"])
        self._mostrar_recomendacoes(dados["recomendacoes"])
        self._mostrar_tabelas(dados)

    def _mostrar_guardado(self, caixa):
        self._guardado_atual = caixa.get("dinheiro_guardado")
        if self._guardado_atual is None:
            self.lbl_guardado.setText(
                "Dinheiro guardado (cofre + banco): não informado — a previsão "
                "de 30 dias conta só o dinheiro dos caixas abertos."
            )
            return
        em = datetime.fromisoformat(caixa["dinheiro_guardado_em"])
        texto = (
            f"Dinheiro guardado (cofre + banco): {formatar_moeda(self._guardado_atual)} "
            f"· estimado a partir do valor conferido em {em:%d/%m/%Y}"
        )
        det = caixa.get("dinheiro_guardado_detalhe")
        if det:
            texto += (
                f" ({formatar_moeda(caixa['dinheiro_guardado_base'])}"
                f" + fechamentos {formatar_moeda(det['fechamentos'])}"
                f" + PIX/cartão {formatar_moeda(det['direto_no_banco'])}"
                f" − contas {formatar_moeda(det['contas_pagas'])}"
                f" − suprimentos {formatar_moeda(det['suprimentos'])})"
            )
        self.lbl_guardado.setText(texto + " · empresa toda")

    def _informar_guardado(self):
        atual = (
            formatar_moeda(self._guardado_atual, com_simbolo=False)
            if self._guardado_atual is not None else ""
        )
        texto, ok = pedir_texto(
            self, "Conferir dinheiro guardado", "Total hoje no cofre + banco (R$)",
            valor=atual, icone_nome="wallet",
            subtitulo="Daqui pra frente o sistema soma os fechamentos e PIX/cartão e "
                      "desconta as contas pagas; confira de vez em quando",
        )
        if not ok:
            return
        valor = valor_digitado(texto)
        if valor is None:
            self._mostrar_erro("Valor inválido. Digite só o número, ex.: 10.000,00")
            return
        rodar_em_thread(
            self, informar_dinheiro_guardado, valor,
            ao_sucesso=self._ao_salvar_guardado, ao_erro=self._ao_erro,
        )

    def _ao_salvar_guardado(self, _resposta):
        self.carregar()

    # ---------------- preenchimento ----------------

    def _mostrar_kpis(self, d):
        vendas, fiado, contas, prev = (
            d["vendas"], d["fiado"], d["contas_pagar"], d["previsao_30_dias"]
        )
        self.card_faturamento.definir_valor(formatar_moeda(vendas["faturamento_liquido"]))
        self.card_faturamento.definir_legenda(
            f"bruto {formatar_moeda(vendas['faturamento_bruto'])} · "
            f"devoluções {formatar_moeda(vendas['devolucoes'])}"
        )
        self.card_vendas.definir_valor(str(vendas["quantidade"]))
        self.card_vendas.definir_legenda(
            f"à vista {formatar_moeda(vendas['a_vista'])} · "
            f"a prazo {formatar_moeda(vendas['a_prazo'])}"
        )
        self.card_ticket.definir_valor(formatar_moeda(vendas["ticket_medio"]))
        self.card_ticket.definir_legenda("faturamento ÷ vendas")
        if vendas["lucro_bruto"] is None:
            self.card_lucro.definir_valor("—")
            self.card_lucro.definir_legenda("produto vendido sem custo cadastrado")
        else:
            self.card_lucro.definir_valor(formatar_moeda(vendas["lucro_bruto"]))
            self.card_lucro.definir_legenda("venda − custo dos produtos (sem despesas)")

        self.card_fiado.definir_valor(formatar_moeda(fiado["saldo_em_aberto"]))
        self.card_fiado.definir_legenda(
            f"{fiado['clientes_devendo']} clientes · empresa toda · não é dinheiro em caixa"
        )
        self.card_recebido.definir_valor(formatar_moeda(d["recebimentos"]["fiado_recebido"]))
        self.card_recebido.definir_legenda(
            f"entrou no período (à vista + fiado): "
            f"{formatar_moeda(d['caixa']['entrou_no_periodo'])}"
        )
        a_pagar = float(contas["vencidas"]["total"]) + float(contas["proximos_30_dias"]["total"])
        self.card_contas.definir_valor(formatar_moeda(a_pagar))
        self.card_contas.definir_legenda(
            f"vencidas {formatar_moeda(contas['vencidas']['total'])} · "
            f"7 dias {formatar_moeda(contas['proximos_7_dias']['total'])}"
        )
        self.card_previsao.definir_valor(formatar_moeda(prev["saldo_previsto"]))
        self.card_previsao.definir_legenda(
            f"entra ~{formatar_moeda(prev['entradas_estimadas'])} · "
            f"sai {formatar_moeda(prev['saidas_previstas'])} · sem cofre/banco"
        )
        self.card_previsao.setToolTip(prev["observacao"])

    def _mostrar_avisos(self, avisos):
        self.secao_avisos.limpar_corpo()
        self.secao_avisos.setVisible(bool(avisos))
        for aviso in avisos:
            self.secao_avisos.corpo.addWidget(_texto(f"• {aviso}", cor=tokens.TEXTO_SECUNDARIO))

    def _mostrar_recomendacoes(self, recomendacoes):
        secao = self.secao_recomendacoes
        secao.limpar_corpo()
        if not recomendacoes:
            secao.adicionar_vazio("Nenhum problema encontrado nos dados deste período.")
            return
        for rec in recomendacoes:
            secao.corpo.addWidget(self._cartao_recomendacao(rec))

    def _cartao_recomendacao(self, rec):
        caixa = QFrame()
        caixa.setObjectName("rec")
        caixa.setStyleSheet(f"""
            QFrame#rec {{
                background:{tokens.FUNDO}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
        """)
        layout = QVBoxLayout(caixa)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        topo = QHBoxLayout()
        rotulo, variante = PRIORIDADES.get(rec["prioridade"], (rec["prioridade"], "neutro"))
        topo.addWidget(Badge(rotulo, variante))
        topo.addWidget(_texto(rec["problema"], tokens.TAMANHO_MD, negrito=True), 1)
        layout.addLayout(topo)

        for evidencia in rec["evidencias"]:
            layout.addWidget(_texto(f"• {evidencia}", cor=tokens.TEXTO_SECUNDARIO))
        layout.addWidget(_texto(f"Impacto: {rec['impacto']}", cor=tokens.TEXTO_SECUNDARIO))
        layout.addWidget(_texto(f"O que fazer: {rec['acao']}", negrito=True))
        layout.addWidget(_texto(
            f"Prazo: {rec['prazo']} · Acompanhar: {rec['indicador']}",
            tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO,
        ))
        return caixa

    def _mostrar_tabelas(self, d):
        lojas = d["lojas"]
        self.secao_lojas.setVisible(bool(lojas))
        _preencher(self.tabela_lojas, [
            [
                l["loja_nome"], formatar_moeda(l["faturamento_liquido"]), l["quantidade"],
                formatar_moeda(l["ticket_medio"]), formatar_moeda(l["a_vista"]),
                formatar_moeda(l["a_prazo"]), formatar_moeda(l["fiado_recebido"]),
                formatar_moeda(l["contas_pendentes_30_dias"]),
                formatar_moeda(l["dinheiro_nas_gavetas"]),
            ]
            for l in lojas
        ])

        _preencher(self.tabela_formas, [
            [f["forma_pagamento"], f["quantidade"], formatar_moeda(f["total"])]
            for f in d["vendas"]["formas_pagamento"]
        ])
        _preencher(self.tabela_contas, [
            [date.fromisoformat(c["vencimento"]).strftime("%d/%m/%Y"),
             c["descricao"] or "—", formatar_moeda(c["valor"])]
            for c in d["contas_pagar"]["proximas"]
        ])

        def faixa(f):
            if f["ate_dias"] is None:
                return f"mais de {f['de_dias'] - 1} dias"
            return f"{f['de_dias']} a {f['ate_dias']} dias"

        _preencher(self.tabela_faixas, [
            [faixa(f), f["clientes"], formatar_moeda(f["total"])]
            for f in d["fiado"]["faixas_atraso"]
        ])
        _preencher(self.tabela_devedores, [
            [dv["nome"], formatar_moeda(dv["saldo"]), f"{dv['dias_em_atraso']} dias",
             "sim" if dv["tem_telefone"] else "não"]
            for dv in d["fiado"]["maiores_devedores"]
        ])
        _preencher(self.tabela_produtos, [
            [p["produto"], p["quantidade"], formatar_moeda(p["total"])]
            for p in d["vendas"]["mais_vendidos"]
        ])
