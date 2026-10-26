from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
)

from services.caixa_service import entradas_caixa, historico_caixa
from services.worker import rodar_em_thread
from design import tokens
from design.widgets import BotaoSecundario, CardKPI
from utils.formatacao import formatar_moeda
from widgets.dialogs.message_dialog import Mensagem
from .comum import NOMES_FORMA_PAGAMENTO


class CaixaMixin:
    """Aba Caixa: historico de caixas, entradas e caixas anteriores."""

    # ==========================================
    # PÁGINA: RELATÓRIO DE CAIXA
    # ==========================================

    def _criar_pagina_caixa(self):

        pagina, layout = self._pagina_rolavel(espacamento=12)

        cabecalho_caixa = QHBoxLayout()

        titulo = QLabel("Dinheiro que entrou")
        titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_LG}px; font-weight:700; color:{tokens.TEXTO};
            background:transparent;
        """)
        cabecalho_caixa.addWidget(titulo)
        cabecalho_caixa.addStretch()

        self.combo_periodo_caixa = QComboBox()
        self.combo_periodo_caixa.addItems(self._periodos_com_meses())
        self.combo_periodo_caixa.setCurrentText("Este mês")
        self.combo_periodo_caixa.setMinimumHeight(34)
        self.combo_periodo_caixa.setCursor(Qt.PointingHandCursor)
        self.combo_periodo_caixa.setStyleSheet(f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:0 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """)
        self.combo_periodo_caixa.currentIndexChanged.connect(self._atualizar_entradas)
        cabecalho_caixa.addWidget(self.combo_periodo_caixa)

        self.combo_loja_caixa = QComboBox()
        self.combo_loja_caixa.setMinimumHeight(34)
        self.combo_loja_caixa.setCursor(Qt.PointingHandCursor)
        self.combo_loja_caixa.setStyleSheet(f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:0 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """)
        self._carregar_combo_lojas(self.combo_loja_caixa)
        self.combo_loja_caixa.currentIndexChanged.connect(
            self._recarregar_historico_caixa
        )
        cabecalho_caixa.addWidget(self.combo_loja_caixa)

        self.bt_caixas_anteriores = BotaoSecundario("Caixas anteriores", icone_nome="calendar")
        self.bt_caixas_anteriores.setMinimumHeight(34)
        self.bt_caixas_anteriores.setToolTip("Ver vendas e recebimentos de cada caixa e reimprimir o fechamento")
        self.bt_caixas_anteriores.clicked.connect(lambda: self.abrir_caixas_anteriores())
        cabecalho_caixa.addWidget(self.bt_caixas_anteriores)

        layout.addLayout(cabecalho_caixa)

        # tudo que entrou de verdade no periodo, somando todos os caixas
        # (ver CaixaService.entradas no backend)
        # linha 1: entrou - saiu = sobrou; linha 2: de onde veio o que entrou
        cards_saldo = QHBoxLayout()
        cards_saldo.setSpacing(14)
        self.card_entrou_total = CardKPI("Total que entrou", "dollar-sign", tokens.PRIMARIA, destaque=True)
        self.card_contas_pagas = CardKPI("Contas pagas", "file-text", tokens.ERRO)
        self.card_sangrias = CardKPI("Sangrias", "arrow-down", tokens.ERRO)
        self.card_sobrou = CardKPI("Resultado do período", "wallet", tokens.SECUNDARIA, destaque=True)
        for card in (
            self.card_entrou_total, self.card_contas_pagas, self.card_sangrias, self.card_sobrou,
        ):
            cards_saldo.addWidget(card, 1)
        layout.addLayout(cards_saldo)

        cards_entradas = QHBoxLayout()
        cards_entradas.setSpacing(14)
        self.card_entrou_dinheiro = CardKPI("Dinheiro", "wallet", tokens.SECUNDARIA_HOVER)
        self.card_entrou_pix = CardKPI("PIX", "trending-up", tokens.PRIMARIA)
        self.card_entrou_cartao = CardKPI("Cartão", "credit-card", tokens.PRIMARIA)
        self.card_entrou_fiado = CardKPI("Fiado recebido", "users", tokens.ALERTA)
        for card in (
            self.card_entrou_dinheiro, self.card_entrou_pix,
            self.card_entrou_cartao, self.card_entrou_fiado,
        ):
            cards_entradas.addWidget(card, 1)
        layout.addLayout(cards_entradas)

        self.lbl_entradas_nota = QLabel("")
        self.lbl_entradas_nota.setWordWrap(True)
        self.lbl_entradas_nota.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SECUNDARIO}; font-size:{tokens.TAMANHO_SM}px;"
        )
        layout.addWidget(self.lbl_entradas_nota)
        layout.addSpacing(10)

        titulo_historico = QLabel("Histórico de caixas")
        titulo_historico.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_LG}px; font-weight:700; color:{tokens.TEXTO};
            background:transparent;
        """)
        layout.addWidget(titulo_historico)

        dica = QLabel("Dê dois cliques em um caixa fechado para ver o detalhe e reimprimir o fechamento.")
        dica.setStyleSheet(f"background:transparent; color:{tokens.TEXTO_SECUNDARIO}; font-size:{tokens.TAMANHO_SM}px;")
        layout.addWidget(dica)

        cards_caixa = QHBoxLayout()
        cards_caixa.setSpacing(14)
        self.card_caixas_total = CardKPI("Caixas no histórico", "wallet", tokens.PRIMARIA)
        self.card_caixas_diferenca = CardKPI("Fechados com diferença", "alert-triangle", tokens.ALERTA)
        self.card_diferenca_total = CardKPI("Diferença acumulada", "dollar-sign", tokens.ERRO)
        for card in (self.card_caixas_total, self.card_caixas_diferenca, self.card_diferenca_total):
            cards_caixa.addWidget(card, 1)
        layout.addLayout(cards_caixa)

        self.tabela_caixa = QTableWidget()
        self.tabela_caixa.setColumnCount(7)
        self.tabela_caixa.setHorizontalHeaderLabels([
            "Abertura",
            "Fechamento",
            "Troco inicial",
            "Esperado",
            "Contado",
            "Diferença",
            "Situação",
        ])
        self._estilizar_tabela(self.tabela_caixa)

        self.tabela_caixa.setMinimumHeight(360)
        self.tabela_caixa.cellDoubleClicked.connect(self._ao_duplo_clique_caixa)
        layout.addWidget(self.tabela_caixa)
        layout.addStretch()

        return pagina

    def _ao_duplo_clique_caixa(self, linha, _coluna):
        if 0 <= linha < len(self.caixas) and self.caixas[linha].get("status") == "FECHADO":
            self.abrir_caixas_anteriores(self.caixas[linha].get("id"))

    def abrir_caixas_anteriores(self, caixa_id=None):
        from telas.caixas_anteriores import CaixasAnterioresDialog
        CaixasAnterioresDialog(parent=self, caixa_id=caixa_id).exec()

    def _atualizar_entradas(self):
        inicio, fim = self._calcular_periodo(self.combo_periodo_caixa)
        rodar_em_thread(
            self, entradas_caixa, inicio, fim, self.combo_loja_caixa.currentData(),
            ao_sucesso=self._ao_atualizar_entradas,
            ao_erro=self._ao_atualizar_entradas_erro,
        )

    def _ao_atualizar_entradas_erro(self, erro):
        self.lbl_entradas_nota.setText(str(erro))

    def _ao_atualizar_entradas(self, dados):
        def valor(chave):
            return float(dados.get(chave) or 0)

        total = valor("total")
        self.card_entrou_total.definir_valor(formatar_moeda(total))
        self.card_entrou_total.definir_legenda(self.combo_periodo_caixa.currentText().lower())
        for card, chave in (
            (self.card_entrou_dinheiro, "dinheiro"), (self.card_entrou_pix, "pix"),
            (self.card_entrou_cartao, "cartao"),
        ):
            card.definir_valor(formatar_moeda(valor(chave)))
            card.definir_legenda(f"{valor(chave) / total * 100:.0f}% do total" if total else "—")
        self.card_contas_pagas.definir_valor(formatar_moeda(valor("contas_pagas")))
        por_forma = dados.get("contas_pagas_por_forma") or {}
        self.card_contas_pagas.definir_legenda(" · ".join(
            f"{formatar_moeda(float(v))} {NOMES_FORMA_PAGAMENTO.get(f, f.capitalize()).lower()}"
            for f, v in sorted(por_forma.items(), key=lambda fv: -float(fv[1]))
        ) or "contas a pagar quitadas")
        self.card_sangrias.definir_valor(formatar_moeda(valor("sangrias")))
        self.card_sangrias.definir_legenda("retiradas do caixa")
        sobrou = valor("sobrou")
        self.card_sobrou.definir_valor(("− " if sobrou < 0 else "") + formatar_moeda(abs(sobrou)))
        # so' desconta o que foi lancado no sistema: despesas pagas fora
        # dele (ou antes das contas a pagar existirem) nao saem daqui
        self.card_sobrou.definir_legenda(
            "gastou mais do que entrou" if sobrou < 0 else "entrou − contas − sangrias"
        )
        self.card_sobrou.setToolTip(
            "Entrou no período menos o que saiu (contas pagas e sangrias). "
            "Negativo quer dizer que o período gastou mais do que entrou -- as "
            "contas foram pagas com dinheiro guardado de antes. Não é o dinheiro "
            "que a loja tem: esse está no BI, em \"Dinheiro guardado\"."
        )
        self.card_entrou_fiado.definir_valor(formatar_moeda(valor("fiado_recebido")))
        self.card_entrou_fiado.definir_legenda("já somado no dinheiro, PIX e cartão")

        nota = (
            "Soma as vendas (menos estornos) e o fiado que os clientes pagaram, de todos os caixas. "
            "Troco inicial e suprimentos não entram. O resultado não é o dinheiro em "
            "mãos (esse está no BI, em \"Dinheiro guardado\")."
        )
        if valor("outros") >= 0.01:
            nota += f" Outras formas: {formatar_moeda(valor('outros'))}."
        if valor("vendas_prazo") >= 0.01:
            nota += f" Vendido a prazo (ainda não entrou): {formatar_moeda(valor('vendas_prazo'))}."
        self.lbl_entradas_nota.setText(nota)

    @staticmethod
    def _data_hora(texto):
        try:
            return datetime.fromisoformat(texto).strftime("%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            return texto or "—"

    def _atualizar_caixa(self):

        self.tabela_caixa.setRowCount(0)

        fechados_com_diferenca = 0
        diferenca_total = 0.0

        for caixa in self.caixas:

            linha = self.tabela_caixa.rowCount()
            self.tabela_caixa.insertRow(linha)

            aberto = caixa.get("status") == "ABERTO"
            esperado = caixa.get("saldo_final")
            contado = caixa.get("valor_contado")

            diferenca = None
            if not aberto and esperado is not None and contado is not None:
                diferenca = float(contado) - float(esperado)
                if abs(diferenca) >= 0.01:
                    fechados_com_diferenca += 1
                    diferenca_total += diferenca

            valores = [
                self._data_hora(caixa.get("data_abertura")),
                "—" if aberto else self._data_hora(caixa.get("data_fechamento")),
                formatar_moeda(caixa.get("saldo_inicial", 0)),
                formatar_moeda(esperado) if esperado is not None else "—",
                formatar_moeda(contado) if contado is not None else "—",
            ]
            for coluna, texto in enumerate(valores):
                self.tabela_caixa.setItem(linha, coluna, QTableWidgetItem(texto))

            if diferenca is None:
                item_dif = QTableWidgetItem("—")
            elif abs(diferenca) < 0.01:
                item_dif = QTableWidgetItem("R$ 0,00")
                item_dif.setForeground(QColor(tokens.SECUNDARIA_HOVER))
            else:
                sinal = "+ " if diferenca > 0 else "− "
                item_dif = QTableWidgetItem(sinal + formatar_moeda(abs(diferenca)))
                item_dif.setForeground(QColor(tokens.PRIMARIA if diferenca > 0 else tokens.ERRO))
            self.tabela_caixa.setItem(linha, 5, item_dif)

            if aberto:
                texto_sit, cor_sit = "● Em aberto", tokens.ALERTA
            elif diferenca is None or abs(diferenca) < 0.01:
                texto_sit, cor_sit = "● Conferido", tokens.SECUNDARIA_HOVER
            else:
                texto_sit = "● Sobra" if diferenca > 0 else "● Falta"
                cor_sit = tokens.PRIMARIA if diferenca > 0 else tokens.ERRO
            item_sit = QTableWidgetItem(texto_sit)
            item_sit.setForeground(QColor(cor_sit))
            self.tabela_caixa.setItem(linha, 6, item_sit)

        self.card_caixas_total.definir_valor(str(len(self.caixas)))
        abertos = sum(1 for c in self.caixas if c.get("status") == "ABERTO")
        self.card_caixas_total.definir_legenda(f"{abertos} em aberto agora")
        self.card_caixas_diferenca.definir_valor(str(fechados_com_diferenca))
        self.card_caixas_diferenca.definir_legenda("sobra ou falta na conferência")
        sinal = "+ " if diferenca_total > 0.009 else ("− " if diferenca_total < -0.009 else "")
        self.card_diferenca_total.definir_valor(sinal + formatar_moeda(abs(diferenca_total)))
        self.card_diferenca_total.definir_legenda("contado − esperado, somando tudo")

        self.tabela_caixa.setCurrentCell(-1, -1)
        self.tabela_caixa.clearSelection()

    def _recarregar_historico_caixa(self):

        if self._carregando_caixa:
            return
        self._carregando_caixa = True

        rodar_em_thread(
            self,
            historico_caixa,
            self.combo_loja_caixa.currentData(),
            ao_sucesso=self._ao_recarregar_caixa_sucesso,
            ao_erro=self._ao_recarregar_caixa_erro,
            ao_finalizar=self._ao_recarregar_caixa_finalizado,
        )

    def _ao_recarregar_caixa_sucesso(self, caixas):
        self.caixas = caixas
        self._atualizar_caixa()
        self._atualizar_entradas()

    def _ao_recarregar_caixa_erro(self, erro):
        Mensagem.erro(
            self, f"Não foi possível carregar o histórico de caixa.\n{erro}"
        )

    def _ao_recarregar_caixa_finalizado(self):
        self._carregando_caixa = False
