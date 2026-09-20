from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTableWidgetItem,
)

from services.extrato_bancario_service import (
    sugerir_candidatos,
    conciliar_transacao,
)
from services.conta_pagar_service import listar_contas_pagar
from services.worker import rodar_em_thread
from widgets.dialogs.pesquisa_window import PesquisaWindow
from widgets.tables.standard_table import StandardTable
from design import tokens
from design.widgets import BotaoPrimario, BotaoSecundario
from utils.formatacao import formatar_moeda


class ConciliarTransacaoDialog(QDialog):
    """Sugestoes automaticas (mesmo valor absoluto, data +-5 dias, ver
    ExtratoBancarioService.sugerir_candidatos) -- pra DEBITO (conta a
    pagar) tem tambem busca manual, ja que contas a pagar tem tela
    propria no frontend; conta a receber nao (fiado ainda nao tem uma
    tela de listagem dedicada), entao so' sugestao automatica."""

    def __init__(self, transacao, parent=None):
        super().__init__(parent)

        self.transacao = transacao
        self.candidatos = []
        self.conciliado = False

        self.setWindowTitle("Conciliar Transação")
        self.resize(520, 460)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Conciliar Transação")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        layout.addWidget(titulo)

        sinal = "+" if transacao["tipo"] == "CREDITO" else "-"
        info = QLabel(
            f"{transacao['data']} -- {transacao.get('descricao') or 'Sem descrição'}\n"
            f"{sinal} {formatar_moeda(abs(float(transacao['valor'])))}"
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
            padding:10px 14px; color:{tokens.TEXTO}; font-weight:700;
        """)
        layout.addWidget(info)

        lbl_sugestoes = QLabel("Sugestões (mesmo valor, data próxima)")
        lbl_sugestoes.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SECUNDARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; font-weight:700;"
        )
        layout.addWidget(lbl_sugestoes)

        self.tabela = StandardTable(["Descrição", "Valor", "Data"])
        layout.addWidget(self.tabela, stretch=1)

        rodape = QHBoxLayout()

        self.bt_selecionar = BotaoPrimario("Conciliar selecionada")
        self.bt_selecionar.setEnabled(False)
        self.bt_selecionar.clicked.connect(self.conciliar_selecionada)
        rodape.addWidget(self.bt_selecionar)

        if transacao["tipo"] == "DEBITO":
            self.bt_manual = BotaoSecundario("Buscar conta a pagar...")
            self.bt_manual.clicked.connect(self.buscar_manualmente)
            rodape.addWidget(self.bt_manual)

        rodape.addStretch()

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.clicked.connect(self.reject)
        rodape.addWidget(bt_cancelar)

        layout.addLayout(rodape)

        self.tabela.itemSelectionChanged.connect(
            lambda: self.bt_selecionar.setEnabled(
                self.tabela.currentRow() >= 0
            )
        )

        self.carregar_sugestoes()

    def carregar_sugestoes(self):
        rodar_em_thread(
            self,
            sugerir_candidatos,
            self.transacao["id"],
            ao_sucesso=self._ao_carregar_sugestoes_sucesso,
        )

    def _ao_carregar_sugestoes_sucesso(self, candidatos):

        self.candidatos = candidatos
        self.tabela.setRowCount(len(candidatos))

        for linha, c in enumerate(candidatos):
            self.tabela.setItem(linha, 0, QTableWidgetItem(c["descricao"]))
            self.tabela.setItem(
                linha, 1, QTableWidgetItem(formatar_moeda(c["valor"]))
            )
            self.tabela.setItem(
                linha, 2,
                QTableWidgetItem(
                    datetime.fromisoformat(c["data"]).strftime("%d/%m/%Y")
                ),
            )

    def conciliar_selecionada(self):

        linha = self.tabela.currentRow()
        if linha < 0:
            return

        candidato = self.candidatos[linha]
        self._conciliar_com(candidato["tipo"], candidato["id"])

    def buscar_manualmente(self):

        rodar_em_thread(
            self,
            listar_contas_pagar,
            ao_sucesso=self._ao_listar_contas_pagar_sucesso,
        )

    def _ao_listar_contas_pagar_sucesso(self, contas):

        pagas = [c for c in contas if c.get("status") == "PAGO"]

        tela = PesquisaWindow(
            titulo="Buscar conta a pagar",
            colunas=["Descrição", "Valor", "Data de pagamento"],
            campos=["descricao", "valor", "data_pagamento"],
            dados=pagas,
            chave_pesquisa="descricao",
        )

        if tela.exec() != QDialog.Accepted:
            return

        self._conciliar_com("PAGAR", tela.selecionado["id"])

    def _conciliar_com(self, tipo, conta_id):

        resposta = QMessageBox.question(
            self, "Conciliar",
            "Conciliar essa transação com a conta selecionada?",
        )
        if resposta != QMessageBox.Yes:
            return

        rodar_em_thread(
            self,
            conciliar_transacao,
            self.transacao["id"],
            conta_id if tipo == "PAGAR" else None,
            conta_id if tipo == "RECEBER" else None,
            ao_sucesso=self._ao_conciliar_sucesso,
            ao_erro=self._ao_conciliar_erro,
        )

    def _ao_conciliar_sucesso(self, response):
        if response.status_code == 200:
            self.conciliado = True
            self.accept()
        else:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_conciliar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))
