from datetime import date, datetime, timedelta
from html import escape

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import BotaoPerigo, BotaoPrimario, BotaoSecundario, Card, CardKPI
from services import (
    api, comprovante_service, impressora_termica_service, preferencias_service,
)
from services.venda_service import (
    cancelar_venda,
    listar_devolucoes,
    listar_vendas_periodo,
    resumo_vendedores,
)
from services.loja_service import listar_lojas
from services.worker import em_paralelo, rodar_em_thread
from telas.devolucao_dialog import DevolucaoDialog
from utils.formatacao import NOMES_FORMA, formatar_moeda
from widgets.tables.standard_table import StandardTable

_NOMES_FORMA = NOMES_FORMA

_NOMES_STATUS = {
    "FINALIZADA": "Finalizada",
    "CANCELADA": "Cancelada",
    "ABERTA": "Suspensa",
}


def _data_curta(data_iso):
    # fiado lancado pela ficha fica sem hora (00:00): mostra so o dia
    dt = datetime.fromisoformat(data_iso)
    return dt.strftime("%d/%m" if (dt.hour, dt.minute) == (0, 0) else "%d/%m %H:%M")


def _forma_da_venda(venda):
    forma = _NOMES_FORMA.get(venda["forma_pagamento"], venda["forma_pagamento"])
    if venda.get("forma_pagamento_2"):
        forma += " + " + _NOMES_FORMA.get(
            venda["forma_pagamento_2"], venda["forma_pagamento_2"]
        )
    return forma


def _estilo_data(campo):
    campo.setCalendarPopup(True)
    campo.setDisplayFormat("dd/MM/yyyy")
    campo.setMinimumHeight(38)
    campo.setStyleSheet(f"""
        QDateEdit {{
            border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
            padding: 0 10px; font-size: {tokens.TAMANHO_BASE}px; color: {tokens.TEXTO};
            background: {tokens.CARD};
        }}
        QDateEdit:focus {{ border-color: {tokens.PRIMARIA}; }}
    """)


class Vendas(QWidget):
    """Histórico de vendas por período: quanto cada vendedora vendeu
    (cada uma entra com o próprio login, então a vendedora é o usuário
    da venda), os itens de cada venda e as ações de devolução/troca e
    cancelamento."""

    voltar = Signal()
    # (crédito, cliente {"id", "nome"} ou None) -- PrincipalWindow abre
    # o PDV com isso (ver PDV.iniciar_troca)
    troca_iniciada = Signal(float, object)

    def __init__(self):
        super().__init__()

        self.vendas = []
        self.nomes_loja = {}
        self.venda_atual = None
        self.devolucoes_atual = []
        self._carregando = False

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        layout.addLayout(self._construir_cabecalho())
        layout.addLayout(self._construir_filtros())

        kpis = QGridLayout()
        kpis.setSpacing(14)
        self.card_total = CardKPI("Vendido no período", "dollar-sign", tokens.PRIMARIA, destaque=True)
        self.card_quantidade = CardKPI("Vendas", "shopping-cart", tokens.SECUNDARIA)
        self.card_devolvido = CardKPI("Devoluções", "refresh-cw", tokens.ALERTA)
        kpis.addWidget(self.card_total, 0, 0)
        kpis.addWidget(self.card_quantidade, 0, 1)
        kpis.addWidget(self.card_devolvido, 0, 2)
        # Vendedor: a lista das proprias vendas com valor, sem os totais
        self._financeiro = api.usuario_tem_permissao("financeiro.ver")
        if self._financeiro:
            layout.addLayout(kpis)
        else:
            for card in (self.card_total, self.card_quantidade, self.card_devolvido):
                card.hide()

        corpo = QHBoxLayout()
        corpo.setSpacing(16)

        self.tabela = StandardTable(
            ["Nº", "Data", "Loja", "Cliente", "Vendedora", "Pagamento", "Total", "Situação"]
        )
        self.tabela.itemSelectionChanged.connect(self._ao_selecionar)
        corpo.addWidget(self.tabela, stretch=3)

        lateral = QVBoxLayout()
        lateral.setSpacing(16)
        # vendedoras sao poucas (2-3 linhas): tamanho fixo, o resto vai pros
        # itens da venda -- antes os dois dividiam e a lista de itens sumia
        card_vendedoras = self._construir_card_vendedoras()
        card_vendedoras.setVisible(self._financeiro)
        lateral.addWidget(card_vendedoras)
        lateral.addWidget(self._construir_card_detalhe(), stretch=1)
        corpo.addLayout(lateral, stretch=2)

        layout.addLayout(corpo, stretch=1)

        # só carrega quando a tela é aberta (ver PrincipalWindow._exibir_pagina)
        self._periodo_rapido(0, carregar=False)

    # ======================================
    # CONSTRUÇÃO
    # ======================================

    def _construir_cabecalho(self):

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(12)

        bt_voltar = QPushButton()
        bt_voltar.setFixedSize(36, 36)
        bt_voltar.setCursor(Qt.PointingHandCursor)
        bt_voltar.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        bt_voltar.setToolTip("Voltar")
        bt_voltar.setAccessibleName("Voltar")
        bt_voltar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        bt_voltar.clicked.connect(self.voltar.emit)

        icone_titulo = QLabel()
        icone_titulo.setFixedSize(36, 36)
        icone_titulo.setAlignment(Qt.AlignCenter)
        icone_titulo.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_SM}px;
        """)
        icone_titulo.setPixmap(icone_pixmap("file-text", cor=tokens.PRIMARIA, tamanho=18))

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Vendas")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        subtitulo = QLabel(
            "Histórico de vendas, total por vendedora, devoluções e trocas."
        )
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        cabecalho.addWidget(bt_voltar)
        cabecalho.addWidget(icone_titulo)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()

        return cabecalho

    def _construir_filtros(self):

        filtros = QHBoxLayout()
        filtros.setSpacing(10)

        for rotulo, dias in (("Hoje", 0), ("7 dias", 6), ("30 dias", 29)):
            bt = BotaoSecundario(rotulo)
            bt.clicked.connect(lambda _=False, d=dias: self._periodo_rapido(d))
            filtros.addWidget(bt)

        filtros.addSpacing(12)

        self.data_inicio = QDateEdit()
        _estilo_data(self.data_inicio)
        self.data_fim = QDateEdit()
        _estilo_data(self.data_fim)

        lbl_ate = QLabel("até")
        lbl_ate.setStyleSheet(f"background:transparent; color:{tokens.TEXTO_SECUNDARIO};")

        filtros.addWidget(self.data_inicio)
        filtros.addWidget(lbl_ate)
        filtros.addWidget(self.data_fim)

        self.filtro_vendedora = QComboBox()
        self.filtro_vendedora.setMinimumHeight(38)
        self.filtro_vendedora.setMinimumWidth(200)
        self.filtro_vendedora.addItem("Todas as vendedoras", None)
        self.filtro_vendedora.currentIndexChanged.connect(self._aplicar_filtro_vendedora)
        filtros.addWidget(self.filtro_vendedora)

        # so' aparece com mais de uma loja (ver _ao_carregar)
        self.filtro_loja = QComboBox()
        self.filtro_loja.setMinimumHeight(38)
        self.filtro_loja.addItem("Todas as lojas", None)
        self.filtro_loja.setVisible(False)
        self.filtro_loja.currentIndexChanged.connect(self.carregar)
        filtros.addWidget(self.filtro_loja)

        bt_buscar = BotaoPrimario("Buscar", icone_nome="search")
        bt_buscar.clicked.connect(self.carregar)
        filtros.addWidget(bt_buscar)

        bt_imprimir = BotaoSecundario("Imprimir", icone_nome="printer")
        bt_imprimir.setToolTip("Imprime as vendas da lista, com os itens de cada uma")
        bt_imprimir.clicked.connect(self.imprimir)
        # imprime o total por forma de pagamento
        bt_imprimir.setVisible(api.usuario_tem_permissao("financeiro.ver"))
        filtros.addWidget(bt_imprimir)

        filtros.addStretch()

        return filtros

    def _titulo_card(self, texto):
        lbl = QLabel(texto)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_MD}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        return lbl

    def _construir_card_vendedoras(self):

        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        layout.addWidget(self._titulo_card("Por vendedora"))

        self.tabela_vendedoras = StandardTable(
            ["Vendedora", "Vendas", "Vendido", "Devolvido", "Líquido"]
        )
        self.tabela_vendedoras.setFixedHeight(100)
        layout.addWidget(self.tabela_vendedoras)

        return card

    def _construir_card_detalhe(self):

        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        self.lbl_detalhe = self._titulo_card("Selecione uma venda")
        layout.addWidget(self.lbl_detalhe)

        self.lbl_detalhe_info = QLabel()
        self.lbl_detalhe_info.setWordWrap(True)
        self.lbl_detalhe_info.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO};
        """)
        layout.addWidget(self.lbl_detalhe_info)

        self.tabela_itens = StandardTable(["Produto", "Qtd", "Valor", "Devolvido"])
        self.tabela_itens.setMinimumHeight(90)
        layout.addWidget(self.tabela_itens, stretch=1)

        botoes = QHBoxLayout()

        self.bt_cancelar = BotaoPerigo("Cancelar venda")
        self.bt_cancelar.clicked.connect(self.cancelar_venda_atual)
        self.bt_cancelar.setVisible(api.usuario_tem_permissao("vendas.cancelar"))

        self.bt_devolver = BotaoPrimario("Devolução / troca", icone_nome="refresh-cw")
        self.bt_devolver.clicked.connect(self.abrir_devolucao)
        self.bt_devolver.setVisible(api.usuario_tem_permissao("vendas.devolver"))

        botoes.addWidget(self.bt_cancelar)
        botoes.addStretch()
        botoes.addWidget(self.bt_devolver)
        layout.addLayout(botoes)

        self._mostrar_detalhe(None)

        return card

    # ======================================
    # CARREGAMENTO
    # ======================================

    def _periodo_rapido(self, dias, carregar=True):
        hoje = date.today()
        self.data_fim.setDate(QDate(hoje.year, hoje.month, hoje.day))
        inicio = hoje - timedelta(days=dias)
        self.data_inicio.setDate(QDate(inicio.year, inicio.month, inicio.day))
        if carregar:
            self.carregar()

    def _periodo(self):
        inicio = self.data_inicio.date().toPython()
        fim = self.data_fim.date().toPython()
        if inicio > fim:
            inicio, fim = fim, inicio
        return inicio, fim

    def carregar(self):

        if self._carregando:
            return

        self._carregando = True
        inicio, fim = self._periodo()
        loja_id = self.filtro_loja.currentData()

        rodar_em_thread(
            self,
            em_paralelo,
            (listar_vendas_periodo, inicio, fim, None, loja_id),
            (resumo_vendedores, inicio, fim, loja_id),
            (listar_lojas, True),
            ao_sucesso=self._ao_carregar,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _ao_carregar(self, resultado):

        vendas, resumo, lojas = resultado

        self.nomes_loja = {l["id"]: l["nome"] for l in lojas}
        if self.filtro_loja.count() == 1 and len(lojas) > 1:
            self.filtro_loja.blockSignals(True)
            for loja in lojas:
                if loja["ativa"]:
                    self.filtro_loja.addItem(loja["nome"], loja["id"])
            self.filtro_loja.blockSignals(False)
        self.filtro_loja.setVisible(len(lojas) > 1)
        self.tabela.setColumnHidden(2, len(lojas) <= 1)

        # suspensas não são venda ainda (sem pagamento, sem baixa)
        self.vendas = [v for v in vendas if v["status"] != "ABERTA"]
        self.resumo = resumo

        selecionada = self.filtro_vendedora.currentData()
        self.filtro_vendedora.blockSignals(True)
        self.filtro_vendedora.clear()
        self.filtro_vendedora.addItem("Todas as vendedoras", None)
        for linha in resumo:
            self.filtro_vendedora.addItem(linha["usuario_nome"] or "—", linha["usuario_id"])
        indice = self.filtro_vendedora.findData(selecionada)
        self.filtro_vendedora.setCurrentIndex(max(indice, 0))
        self.filtro_vendedora.blockSignals(False)

        self._preencher_vendedoras()
        self._aplicar_filtro_vendedora()

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar as vendas.\n\n{erro}")

    def _ao_carregar_finalizado(self):
        self._carregando = False

    def _preencher_vendedoras(self):

        self.tabela_vendedoras.setRowCount(len(self.resumo))

        for linha, item in enumerate(self.resumo):
            valores = [
                item["usuario_nome"] or "—",
                str(item["quantidade_vendas"]),
                formatar_moeda(float(item["total_vendido"])),
                formatar_moeda(float(item["total_devolvido"])),
                formatar_moeda(float(item["total_liquido"])),
            ]
            for coluna, texto in enumerate(valores):
                self.tabela_vendedoras.setItem(linha, coluna, QTableWidgetItem(texto))

        self.card_total.definir_valor(
            formatar_moeda(sum(float(i["total_liquido"]) for i in self.resumo))
        )
        self.card_quantidade.definir_valor(
            str(sum(i["quantidade_vendas"] for i in self.resumo))
        )
        self.card_devolvido.definir_valor(
            formatar_moeda(sum(float(i["total_devolvido"]) for i in self.resumo))
        )

    def _vendas_filtradas(self):
        usuario_id = self.filtro_vendedora.currentData()
        if usuario_id is None:
            return self.vendas
        return [v for v in self.vendas if v.get("usuario_id") == usuario_id]

    def _aplicar_filtro_vendedora(self, *_):

        vendas = self._vendas_filtradas()

        self.tabela.blockSignals(True)
        self.tabela.setRowCount(len(vendas))

        for linha, venda in enumerate(vendas):
            data = datetime.fromisoformat(venda["data"]).strftime("%d/%m %H:%M")
            valores = [
                str(venda["id"]),
                data,
                self.nomes_loja.get(venda.get("loja_id"), "—"),
                venda.get("cliente_nome") or "—",
                venda.get("usuario_nome") or "—",
                _forma_da_venda(venda),
                formatar_moeda(float(venda["valor_total"])),
                _NOMES_STATUS.get(venda["status"], venda["status"]),
            ]
            for coluna, texto in enumerate(valores):
                item = QTableWidgetItem(texto)
                item.setData(Qt.UserRole, venda["id"])
                if venda["status"] == "CANCELADA":
                    item.setForeground(Qt.gray)
                self.tabela.setItem(linha, coluna, item)

        self.tabela.blockSignals(False)
        self.tabela.clearSelection()
        self._mostrar_detalhe(None)

    # ======================================
    # DETALHE DA VENDA
    # ======================================

    def _ao_selecionar(self):

        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            self._mostrar_detalhe(None)
            return

        venda_id = self.tabela.item(linhas[0].row(), 0).data(Qt.UserRole)
        venda = next((v for v in self.vendas if v["id"] == venda_id), None)

        self.venda_atual = venda
        self.devolucoes_atual = []
        self._mostrar_detalhe(venda)

        rodar_em_thread(
            self,
            listar_devolucoes,
            venda_id,
            ao_sucesso=self._ao_carregar_devolucoes,
        )

    def _ao_carregar_devolucoes(self, devolucoes):
        if self.venda_atual and devolucoes and devolucoes[0]["venda_id"] != self.venda_atual["id"]:
            return
        self.devolucoes_atual = devolucoes
        self._mostrar_detalhe(self.venda_atual)

    def _mostrar_detalhe(self, venda):

        self.bt_cancelar.setEnabled(False)
        self.bt_devolver.setEnabled(False)

        if venda is None:
            self.venda_atual = None
            self.lbl_detalhe.setText("Selecione uma venda")
            self.lbl_detalhe_info.setText("Clique numa venda da lista para ver os itens.")
            self.tabela_itens.setRowCount(0)
            return

        devolvido = {}
        for devolucao in self.devolucoes_atual:
            for item in devolucao["itens"]:
                devolvido[item["item_venda_id"]] = (
                    devolvido.get(item["item_venda_id"], 0) + item["quantidade"]
                )

        self.lbl_detalhe.setText(f"Venda #{venda['id']}")

        info = [
            datetime.fromisoformat(venda["data"]).strftime("%d/%m/%Y %H:%M"),
            f"Vendedora: {venda.get('usuario_nome') or '—'}",
            f"Cliente: {venda.get('cliente_nome') or '—'}",
            f"{_forma_da_venda(venda)} · {formatar_moeda(float(venda['valor_total']))}",
        ]
        if venda["status"] == "CANCELADA":
            info.append(
                f"Cancelada por {venda.get('cancelado_por_nome') or '—'}"
                + (f": {venda['motivo_cancelamento']}" if venda.get("motivo_cancelamento") else "")
            )
        total_devolvido = sum(float(d["valor_total"]) for d in self.devolucoes_atual)
        if total_devolvido:
            info.append(f"Devolvido: {formatar_moeda(total_devolvido)}")
        if not venda["itens"]:
            info.insert(1, "Lançada pela ficha da cliente (fiado)")
        self.lbl_detalhe_info.setText("\n".join(info))

        if not venda["itens"]:
            # venda lançada pela ficha da cliente (compra fiada a mão):
            # sem produto cadastrado, o que foi vendido está na descrição
            self.tabela_itens.setRowCount(1)
            for coluna, texto in enumerate([
                venda.get("observacao") or "Compra no fiado",
                "",
                formatar_moeda(float(venda["valor_total"])),
                "",
            ]):
                self.tabela_itens.setItem(0, coluna, QTableWidgetItem(texto))
        else:
            self.tabela_itens.setRowCount(len(venda["itens"]))

        for linha, item in enumerate(venda["itens"]):
            valores = [
                item.get("produto_nome") or f"#{item['produto_id']}",
                str(item["quantidade"]),
                formatar_moeda(float(item["subtotal"])),
                str(devolvido.get(item["id"], 0) or ""),
            ]
            for coluna, texto in enumerate(valores):
                self.tabela_itens.setItem(linha, coluna, QTableWidgetItem(texto))

        finalizada = venda["status"] == "FINALIZADA"
        resta_devolver = any(
            item["quantidade"] > devolvido.get(item["id"], 0) for item in venda["itens"]
        )
        self.bt_devolver.setEnabled(finalizada and resta_devolver)
        self.bt_cancelar.setEnabled(finalizada and not self.devolucoes_atual)

    # ======================================
    # AÇÕES
    # ======================================

    def imprimir(self):
        vendas = self._vendas_filtradas()
        if not vendas:
            QMessageBox.information(self, "Imprimir", "Nenhuma venda nesse período.")
            return

        # só as vendas -- devolução/troca fica fora da impressão (pedido do usuário)
        relatorio = self._dados_relatorio(vendas)
        config_impressora = preferencias_service.carregar_impressora_termica()

        if not (config_impressora and config_impressora.get("ativa")):
            comprovante_service.imprimir(self._html_relatorio(relatorio), self)
            return

        # mesma termica de 80mm do cupom/fechamento; o nome da loja vem do
        # servidor (callbacks precisam ser metodos -- ver rodar_em_thread)
        self._impressao = (relatorio, config_impressora)
        rodar_em_thread(
            self, api.configuracoes,
            ao_sucesso=self._imprimir_na_termica, ao_erro=self._imprimir_na_termica_sem_loja,
        )

    def _imprimir_na_termica_sem_loja(self, _erro):
        self._imprimir_na_termica({})

    def _imprimir_na_termica(self, config_loja):
        relatorio, config_impressora = self._impressao
        ok, erro = impressora_termica_service.imprimir_relatorio_vendas(
            relatorio, config_loja or {}, config_impressora
        )
        if ok:
            return
        # se falhar, oferece a janela normal do Windows (igual fechar_caixa.py)
        resposta = QMessageBox.question(
            self, "Falha na impressora térmica",
            f"{erro}\n\nQuer tentar imprimir pela janela normal do Windows?",
        )
        if resposta == QMessageBox.Yes:
            comprovante_service.imprimir(self._html_relatorio(relatorio), self)

    def _dados_relatorio(self, vendas):
        """Vendas da lista (periodo + vendedora escolhidos) com os itens
        de cada uma e o total por forma de pagamento -- base do HTML e do
        cupom da termica."""

        inicio, fim = self._periodo()
        periodo = inicio.strftime("%d/%m/%Y")
        if fim != inicio:
            periodo += " a " + fim.strftime("%d/%m/%Y")

        por_forma = {}
        blocos = []
        for venda in vendas:
            cancelada = venda["status"] == "CANCELADA"
            forma = _forma_da_venda(venda)
            total = float(venda["valor_total"])
            if not cancelada:
                por_forma[forma] = por_forma.get(forma, 0) + total

            itens = [
                (
                    f"{item['quantidade']}x "
                    + (item.get("produto_nome") or f"#{item.get('produto_id')}"),
                    float(item["subtotal"]),
                )
                for item in venda["itens"]
            ] or [(venda.get("observacao") or "Compra no fiado", total)]

            blocos.append({
                "titulo": f"#{venda['id']} " + _data_curta(venda["data"]),
                "cliente": venda.get("cliente_nome") or "—",
                "vendedora": venda.get("usuario_nome") or "—",
                "forma": forma,
                "total": total,
                "itens": itens,
                "cancelada": cancelada,
            })

        return {
            "periodo": periodo,
            "vendedora": self.filtro_vendedora.currentText(),
            "vendas": blocos,
            "por_forma": sorted(por_forma.items()),
            "quantidade": sum(1 for b in blocos if not b["cancelada"]),
            "total": sum(por_forma.values()),
        }

    def _html_relatorio(self, relatorio):

        linhas = []
        for venda in relatorio["vendas"]:
            riscado = "color:#999; text-decoration:line-through;" if venda["cancelada"] else ""
            linhas.append(
                f"<tr style='background:#f0f0f0; {riscado}'>"
                f"<td><b>{venda['titulo']}</b></td>"
                f"<td>{escape(venda['cliente'])}</td>"
                f"<td>{escape(venda['vendedora'])}</td>"
                f"<td>{venda['forma']}{' (CANCELADA)' if venda['cancelada'] else ''}</td>"
                f"<td align='right'><b>{formatar_moeda(venda['total'])}</b></td></tr>"
            )
            for texto, valor in venda["itens"]:
                linhas.append(
                    f"<tr style='{riscado}'><td colspan='4'>&nbsp;&nbsp;{escape(texto)}</td>"
                    f"<td align='right'>{formatar_moeda(valor)}</td></tr>"
                )

        resumo = "".join(
            f"<tr><td>{forma}</td><td align='right'>{formatar_moeda(total)}</td></tr>"
            for forma, total in relatorio["por_forma"]
        )

        return f"""
        <h2 style="text-align:center; margin-bottom:0;">Vendas — {relatorio['periodo']}</h2>
        <div style="text-align:center; color:#666;">{escape(relatorio['vendedora'])}</div>
        <hr>
        <table width="100%" border="1" cellspacing="0" cellpadding="4">
            <tr style="background:#ddd;">
                <th>Venda</th><th>Cliente</th><th>Vendedora</th><th>Pagamento</th><th>Total</th>
            </tr>
            {''.join(linhas)}
        </table>
        <h3>Total por forma de pagamento</h3>
        <table width="60%" cellspacing="4">
            {resumo}
            <tr><td><b>Total ({relatorio['quantidade']} vendas)</b></td>
                <td align="right"><b>{formatar_moeda(relatorio['total'])}</b></td></tr>
        </table>
        """

    def abrir_devolucao(self):

        venda = self.venda_atual
        if venda is None:
            return

        dialogo = DevolucaoDialog(venda, self.devolucoes_atual, parent=self)
        if dialogo.exec() != DevolucaoDialog.Accepted:
            return

        if dialogo.troca:
            cliente = (
                {"id": venda["cliente_id"], "nome": venda.get("cliente_nome")}
                if venda.get("cliente_id") else None
            )
            self.troca_iniciada.emit(dialogo.valor_devolvido, cliente)
        else:
            QMessageBox.information(
                self,
                "Devolução registrada",
                f"Devolução de {formatar_moeda(dialogo.valor_devolvido)} registrada. "
                "As peças voltaram para o estoque.",
            )

        self.carregar()

    def cancelar_venda_atual(self):

        venda = self.venda_atual
        if venda is None:
            return

        motivo, ok = QInputDialog.getText(
            self,
            "Cancelar venda",
            f"Cancelar a venda #{venda['id']} inteira? Todas as peças voltam "
            "para o estoque e o pagamento é estornado.\n\nMotivo:",
        )
        if not ok:
            return

        response = cancelar_venda(venda["id"], motivo.strip() or None)

        if response.status_code != 200:
            try:
                erro = response.json().get("detail") or response.text
            except Exception:
                erro = response.text
            QMessageBox.warning(self, "Cancelar venda", erro)
            return

        QMessageBox.information(self, "Cancelar venda", "Venda cancelada.")
        self.carregar()
