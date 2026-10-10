from datetime import datetime

from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QTableWidgetItem

from design import tokens
from design.widgets import BotaoPerigo, BotaoSecundario, CardKPI, DialogoPadrao
from services.conta_pagar_service import (
    cancelar_parcelas_restantes,
    listar_parcelamento,
)
from services.worker import rodar_em_thread
from utils.formatacao import formatar_moeda
from widgets.tables.standard_table import StandardTable

_SITUACAO = {"PAGO": "Paga", "PENDENTE": "Em aberto", "CANCELADO": "Cancelada"}


class ParcelamentoDialog(DialogoPadrao):
    """Todas as parcelas de um boleto parcelado juntas: quanto já foi
    pago, quanto falta, e cancelar as que faltam de uma vez (acordo com
    o fornecedor, compra devolvida)."""

    def __init__(self, conta, parent=None):

        nome = (conta.get("descricao") or "Parcelamento").rsplit(" ", 1)[0]

        super().__init__(
            f"Parcelamento — {nome}",
            "Todas as parcelas desse boleto",
            "file-text", tokens.PRIMARIA, tokens.PRIMARIA_CLARA,
            largura=DialogoPadrao.GRANDE, parent=parent,
        )

        self.parcelamento_id = conta["parcelamento_id"]
        self.alterou = False

        kpis = QHBoxLayout()
        kpis.setSpacing(12)
        self.card_total = CardKPI("Total", "file-text", tokens.PRIMARIA)
        self.card_pago = CardKPI("Já pago", "check", tokens.SECUNDARIA)
        self.card_falta = CardKPI("Falta pagar", "wallet", tokens.ALERTA, destaque=True)
        for card in (self.card_total, self.card_pago, self.card_falta):
            kpis.addWidget(card)
        self.corpo.addLayout(kpis)

        self.tabela = StandardTable(["Parcela", "Vencimento", "Valor", "Situação"])
        self.tabela.setMinimumHeight(240)
        self.corpo.addWidget(self.tabela, stretch=1)

        self.lbl_resumo = QLabel()
        self.lbl_resumo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO};
        """)
        self.corpo.addWidget(self.lbl_resumo)

        self.bt_cancelar_restantes = BotaoPerigo("Cancelar parcelas que faltam")
        self.bt_cancelar_restantes.clicked.connect(self.cancelar_restantes)
        self.bt_cancelar_restantes.setEnabled(False)

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.clicked.connect(self.accept)

        acoes = QHBoxLayout()
        acoes.addWidget(self.bt_cancelar_restantes)
        acoes.addStretch()
        self.corpo.addLayout(acoes)
        self.definir_botoes(bt_fechar).setVisible(False)

        self.ajustar_altura()
        self.carregar()

    def carregar(self):
        rodar_em_thread(
            self,
            listar_parcelamento,
            self.parcelamento_id,
            ao_sucesso=self._ao_carregar,
            ao_erro=self._ao_erro,
        )

    def _ao_carregar(self, parcelas):

        self.parcelas = parcelas
        self.tabela.setRowCount(len(parcelas))

        for linha, parcela in enumerate(parcelas):
            vencimento = datetime.fromisoformat(parcela["data_vencimento"]).strftime("%d/%m/%Y")
            valores = [
                f"{parcela.get('parcela_numero') or linha + 1}/{parcela.get('parcela_total') or len(parcelas)}",
                vencimento,
                formatar_moeda(float(parcela["valor"])),
                _SITUACAO.get(parcela["status"], parcela["status"]),
            ]
            for coluna, texto in enumerate(valores):
                self.tabela.setItem(linha, coluna, QTableWidgetItem(texto))

        validas = [p for p in parcelas if p["status"] != "CANCELADO"]
        pagas = [p for p in parcelas if p["status"] == "PAGO"]
        pendentes = [p for p in parcelas if p["status"] == "PENDENTE"]

        self.card_total.lbl_valor.setText(formatar_moeda(sum(float(p["valor"]) for p in validas)))
        self.card_pago.lbl_valor.setText(formatar_moeda(sum(float(p["valor"]) for p in pagas)))
        self.card_falta.lbl_valor.setText(formatar_moeda(sum(float(p["valor"]) for p in pendentes)))
        self.lbl_resumo.setText(
            f"{len(pagas)} de {len(validas)} parcela(s) paga(s) · "
            f"{len(pendentes)} em aberto"
        )
        self.bt_cancelar_restantes.setEnabled(bool(pendentes))

    def _ao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def cancelar_restantes(self):

        pendentes = [p for p in getattr(self, "parcelas", []) if p["status"] == "PENDENTE"]
        if not pendentes:
            return

        resposta = QMessageBox.question(
            self,
            "Cancelar parcelas",
            f"Cancelar as {len(pendentes)} parcela(s) que faltam "
            f"({formatar_moeda(sum(float(p['valor']) for p in pendentes))})? "
            "As que já foram pagas continuam como estão.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        response = cancelar_parcelas_restantes(self.parcelamento_id)
        if response.status_code != 200:
            try:
                erro = response.json().get("detail") or response.text
            except Exception:
                erro = response.text
            QMessageBox.warning(self, "Cancelar parcelas", erro)
            return

        self.alterou = True
        self.carregar()
