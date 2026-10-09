from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
)

from design import tokens
from design.widgets import BotaoPrimario, BotaoSecundario, CampoTexto
from services.venda_service import registrar_devolucao
from services.worker import rodar_em_thread
from utils.formatacao import formatar_moeda
from widgets.tables.standard_table import StandardTable

# (forma, rótulo) -- PRAZO só aparece quando a venda tem cliente
_FORMAS = [
    ("DINHEIRO", "Dinheiro"),
    ("PIX", "Pix"),
    ("DEBITO", "Cartão de débito"),
    ("CREDITO", "Cartão de crédito"),
    ("PRAZO", "Abater do fiado da cliente"),
]


def quantidades_devolvidas(devolucoes):
    """item_venda_id -> quantidade já devolvida."""

    total = {}
    for devolucao in devolucoes:
        for item in devolucao["itens"]:
            total[item["item_venda_id"]] = (
                total.get(item["item_venda_id"], 0) + item["quantidade"]
            )
    return total


def fator_desconto(venda):
    """Quanto de cada R$ 1 de item a cliente pagou de fato (desconto ou
    acréscimo da venda rateado) -- mesma conta do backend
    (DevolucaoService), só pra mostrar o valor antes de confirmar."""

    soma = sum(float(item["subtotal"]) for item in venda["itens"])
    return float(venda["valor_total"]) / soma if soma else 0.0


class DevolucaoDialog(QDialog):
    """Escolhe quais peças da venda voltam e como a cliente recebe.
    "Trocar agora" registra a devolução em dinheiro e quem abriu a tela
    leva o valor pro PDV como crédito (ver PDV.iniciar_troca).

    Depois do accept(): self.troca (bool) e self.valor_devolvido."""

    def __init__(self, venda, devolucoes, parent=None):
        super().__init__(parent)

        self.venda = venda
        self.troca = False
        self.valor_devolvido = 0.0
        self._fator = fator_desconto(venda)

        ja_devolvido = quantidades_devolvidas(devolucoes)
        self._itens = [
            (item, item["quantidade"] - ja_devolvido.get(item["id"], 0))
            for item in venda["itens"]
        ]

        self.setWindowTitle(f"Devolução / troca — venda #{venda['id']}")
        self.resize(760, 560)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        titulo = QLabel(f"Devolução / troca — venda #{venda['id']}")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        layout.addWidget(titulo)

        ajuda = QLabel(
            "Escolha quantas peças de cada item voltam. As peças voltam "
            "para o estoque."
        )
        ajuda.setWordWrap(True)
        ajuda.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(ajuda)

        self.tabela = StandardTable(
            ["Produto", "Vendido", "Já devolvido", "Devolver", "Valor"]
        )
        self.tabela.setRowCount(len(self._itens))
        self.spins = []

        for linha, (item, restante) in enumerate(self._itens):
            self.tabela.setItem(
                linha, 0, QTableWidgetItem(item.get("produto_nome") or f"#{item['produto_id']}")
            )
            self.tabela.setItem(linha, 1, QTableWidgetItem(str(item["quantidade"])))
            self.tabela.setItem(
                linha, 2, QTableWidgetItem(str(item["quantidade"] - restante))
            )

            spin = QSpinBox()
            spin.setRange(0, max(restante, 0))
            spin.setEnabled(restante > 0)
            spin.valueChanged.connect(self._atualizar_total)
            self.tabela.setCellWidget(linha, 3, spin)
            self.spins.append(spin)

            self.tabela.setItem(linha, 4, QTableWidgetItem(formatar_moeda(0)))

        self.tabela.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self.tabela, stretch=1)

        linha_forma = QHBoxLayout()

        lbl_forma = QLabel("Devolver o dinheiro por:")
        lbl_forma.setStyleSheet(f"background:transparent; color:{tokens.TEXTO};")
        linha_forma.addWidget(lbl_forma)

        self.forma = QComboBox()
        self.forma.setMinimumHeight(38)
        for valor, rotulo in _FORMAS:
            if valor == "PRAZO" and not venda.get("cliente_id"):
                continue
            self.forma.addItem(rotulo, valor)
        if "PRAZO" in (venda.get("forma_pagamento"), venda.get("forma_pagamento_2")):
            self.forma.setCurrentIndex(self.forma.findData("PRAZO"))
        linha_forma.addWidget(self.forma, stretch=1)

        layout.addLayout(linha_forma)

        self.motivo = CampoTexto("Motivo (opcional) — ex.: tamanho errado")
        layout.addWidget(self.motivo)

        self.lbl_total = QLabel()
        self.lbl_total.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        layout.addWidget(self.lbl_total)

        botoes = QHBoxLayout()
        botoes.addStretch()

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.clicked.connect(self.reject)

        self.bt_devolver = BotaoSecundario("Só devolver")
        self.bt_devolver.clicked.connect(lambda: self.confirmar(troca=False))

        self.bt_trocar = BotaoPrimario("Trocar agora")
        self.bt_trocar.setToolTip(
            "Registra a devolução e abre o PDV com o valor da peça como "
            "crédito. A cliente paga só a diferença."
        )
        self.bt_trocar.clicked.connect(lambda: self.confirmar(troca=True))

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(self.bt_devolver)
        botoes.addWidget(self.bt_trocar)
        layout.addLayout(botoes)

        self._atualizar_total()

    def _itens_escolhidos(self):
        return [
            {"item_venda_id": item["id"], "quantidade": spin.value()}
            for (item, _restante), spin in zip(self._itens, self.spins)
            if spin.value() > 0
        ]

    def _atualizar_total(self):

        total = 0.0

        for linha, ((item, _restante), spin) in enumerate(zip(self._itens, self.spins)):
            valor = round(float(item["valor_unitario"]) * spin.value() * self._fator, 2)
            total += valor
            self.tabela.item(linha, 4).setText(formatar_moeda(valor))

        self._total = round(total, 2)
        self.lbl_total.setText(f"Valor a devolver: {formatar_moeda(self._total)}")

        tem_itens = self._total > 0 or bool(self._itens_escolhidos())
        self.bt_devolver.setEnabled(tem_itens)
        self.bt_trocar.setEnabled(tem_itens)

    def confirmar(self, troca):

        itens = self._itens_escolhidos()

        if not itens:
            QMessageBox.warning(self, "Devolução", "Escolha pelo menos uma peça.")
            return

        # na troca o valor fica como crédito da venda nova, que entra
        # como dinheiro no pagamento -- por isso a devolução é em dinheiro
        forma = "DINHEIRO" if troca else self.forma.currentData()
        rotulo = "Dinheiro (crédito da troca)" if troca else self.forma.currentText()

        resposta = QMessageBox.question(
            self,
            "Confirmar devolução",
            f"Devolver {formatar_moeda(self._total)} por {rotulo}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        self._troca_pedida = troca
        self.bt_devolver.setEnabled(False)
        self.bt_trocar.setEnabled(False)
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        rodar_em_thread(
            self,
            registrar_devolucao,
            self.venda["id"],
            itens,
            forma,
            self.motivo.text().strip() or None,
            ao_sucesso=self._ao_registrar,
            ao_erro=self._ao_erro,
            ao_finalizar=self._ao_finalizar,
        )

    def _ao_registrar(self, response):

        if response.status_code == 200:
            self.troca = self._troca_pedida
            self.valor_devolvido = float(response.json()["valor_total"])
            self.accept()
            return

        try:
            erro = response.json().get("detail") or response.text
        except Exception:
            erro = response.text

        QMessageBox.warning(self, "Devolução", f"Não foi possível registrar.\n\n{erro}")

    def _ao_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível registrar.\n\n{erro}")

    def _ao_finalizar(self):
        QApplication.restoreOverrideCursor()
        if self.isVisible():
            self._atualizar_total()
