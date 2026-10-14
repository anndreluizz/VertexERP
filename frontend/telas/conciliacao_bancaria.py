from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QDialog,
    QTableWidgetItem,
)

from services.extrato_bancario_service import (
    preview_extrato,
    importar_extrato,
    listar_transacoes,
    ignorar_transacao,
    desconciliar_transacao,
)
from services.worker import rodar_em_thread
from telas.conciliar_transacao_bancaria import ConciliarTransacaoDialog
from widgets.tables.standard_table import StandardTable
from design import tokens
from design.widgets import BotaoPrimario, BotaoSecundario
from utils.formatacao import formatar_moeda

_FILTROS_STATUS = [
    ("Pendentes", "PENDENTE"),
    ("Conciliadas", "CONCILIADA"),
    ("Ignoradas", "IGNORADA"),
    ("Todas", None),
]

_ROTULO_STATUS = {
    "PENDENTE": "Pendente",
    "CONCILIADA": "Conciliada",
    "IGNORADA": "Ignorada",
}


class ConciliacaoBancaria(QWidget):

    def __init__(self):
        super().__init__()

        self.transacoes = []
        self._carregando = False

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        titulo = QLabel("Conciliação Bancária")
        titulo.setStyleSheet(
            f"background:transparent; font-size:{tokens.TAMANHO_XL}px; "
            f"font-weight:800; color:{tokens.TEXTO};"
        )
        layout.addWidget(titulo)

        subtitulo = QLabel(
            "Importa o extrato do banco (arquivo OFX) e casa cada linha "
            "de saída com uma conta a pagar já paga."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(
            f"background:transparent; font-size:{tokens.TAMANHO_SM}px; "
            f"color:{tokens.TEXTO_TERCIARIO};"
        )
        layout.addWidget(subtitulo)

        # ==========================================
        # BARRA SUPERIOR: importar + filtro
        # ==========================================
        barra = QHBoxLayout()
        barra.setSpacing(12)

        self.bt_importar = BotaoPrimario("Importar Extrato (OFX)")
        self.bt_importar.clicked.connect(self.importar)
        barra.addWidget(self.bt_importar)

        barra.addStretch()

        barra.addWidget(QLabel("Status:"))

        self.combo_status = QComboBox()
        self.combo_status.setMinimumHeight(38)
        for rotulo, _ in _FILTROS_STATUS:
            self.combo_status.addItem(rotulo)
        self.combo_status.currentIndexChanged.connect(self.carregar)
        barra.addWidget(self.combo_status)

        layout.addLayout(barra)

        # ==========================================
        # TABELA
        # ==========================================
        self.tabela = StandardTable(
            ["Data", "Descrição", "Valor", "Status", "Conciliado com"]
        )
        layout.addWidget(self.tabela, stretch=1)

        self.tabela.itemSelectionChanged.connect(self._ao_selecionar)

        # ==========================================
        # ACOES
        # ==========================================
        acoes = QHBoxLayout()
        acoes.setSpacing(8)

        self.bt_conciliar = BotaoPrimario("Conciliar")
        self.bt_conciliar.setEnabled(False)
        self.bt_conciliar.clicked.connect(self.conciliar)
        acoes.addWidget(self.bt_conciliar)

        self.bt_ignorar = BotaoSecundario("Ignorar")
        self.bt_ignorar.setEnabled(False)
        self.bt_ignorar.clicked.connect(self.ignorar)
        acoes.addWidget(self.bt_ignorar)

        self.bt_desconciliar = BotaoSecundario("Desconciliar")
        self.bt_desconciliar.setEnabled(False)
        self.bt_desconciliar.clicked.connect(self.desconciliar)
        acoes.addWidget(self.bt_desconciliar)

        acoes.addStretch()

        layout.addLayout(acoes)

        self.carregar()

    # ==========================================
    # CARREGAR
    # ==========================================
    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self.bt_importar.setEnabled(False)

        _, status = _FILTROS_STATUS[self.combo_status.currentIndex()]

        rodar_em_thread(
            self,
            listar_transacoes,
            status,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _ao_carregar_sucesso(self, transacoes):

        self.transacoes = transacoes
        self.tabela.setRowCount(len(transacoes))

        for linha, t in enumerate(transacoes):

            sinal = "+" if t["tipo"] == "CREDITO" else "-"
            valor_texto = f"{sinal} {formatar_moeda(abs(float(t['valor'])))}"

            conciliado_com = t.get("conta_pagar_descricao") or ""

            self.tabela.setItem(
                linha, 0,
                QTableWidgetItem(
                    datetime.fromisoformat(t["data"]).strftime("%d/%m/%Y")
                ),
            )
            self.tabela.setItem(
                linha, 1, QTableWidgetItem(t.get("descricao") or "")
            )
            self.tabela.setItem(linha, 2, QTableWidgetItem(valor_texto))
            self.tabela.setItem(
                linha, 3,
                QTableWidgetItem(_ROTULO_STATUS.get(t["status"], t["status"])),
            )
            self.tabela.setItem(linha, 4, QTableWidgetItem(conciliado_com))

        self._ao_selecionar()

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar o extrato.\n{erro}"
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self.bt_importar.setEnabled(True)

    def _ao_selecionar(self):

        linha = self.tabela.currentRow()
        status = self.transacoes[linha]["status"] if linha >= 0 else None

        self.bt_conciliar.setEnabled(status == "PENDENTE")
        self.bt_ignorar.setEnabled(status == "PENDENTE")
        self.bt_desconciliar.setEnabled(status == "CONCILIADA")

    def _transacao_selecionada(self):
        linha = self.tabela.currentRow()
        return self.transacoes[linha] if linha >= 0 else None

    # ==========================================
    # IMPORTAR
    # ==========================================
    def importar(self):

        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar extrato", "", "OFX (*.ofx)"
        )
        if not caminho:
            return

        try:
            conteudo = Path(caminho).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            conteudo = Path(caminho).read_text(encoding="latin-1")
        except OSError as e:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível ler o arquivo.\n{e}"
            )
            return

        self._conteudo_importacao_pendente = conteudo
        self.bt_importar.setEnabled(False)

        rodar_em_thread(
            self,
            preview_extrato,
            conteudo,
            ao_sucesso=self._ao_preview_sucesso,
            ao_erro=self._ao_importar_erro,
            ao_finalizar=self._ao_importar_finalizado,
        )

    def _ao_preview_sucesso(self, response):

        if response.status_code != 200:
            self._exibir_erro(response)
            return

        preview = response.json()

        if preview["total_novas"] == 0:
            QMessageBox.information(
                self, "Nada a importar",
                "Todas as transações desse arquivo já foram importadas.",
            )
            return

        resposta = QMessageBox.question(
            self, "Importar extrato",
            f"{preview['total_novas']} transações novas, "
            f"{preview['total_ja_importadas']} já importadas antes. "
            "Importar as novas?",
        )
        if resposta != QMessageBox.Yes:
            return

        self.bt_importar.setEnabled(False)

        rodar_em_thread(
            self,
            importar_extrato,
            self._conteudo_importacao_pendente,
            ao_sucesso=self._ao_importar_sucesso,
            ao_erro=self._ao_importar_erro,
            ao_finalizar=self._ao_importar_finalizado,
        )

    def _ao_importar_sucesso(self, response):
        if response.status_code == 200:
            total = response.json()["total_importadas"]
            QMessageBox.information(
                self, "Sucesso",
                f"{total} transações importadas.",
            )
            self.carregar()
        else:
            self._exibir_erro(response)

    def _ao_importar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_importar_finalizado(self):
        if not self._carregando:
            self.bt_importar.setEnabled(True)

    # ==========================================
    # CONCILIAR / IGNORAR / DESCONCILIAR
    # ==========================================
    def conciliar(self):

        transacao = self._transacao_selecionada()
        if transacao is None:
            return

        dialogo = ConciliarTransacaoDialog(transacao, parent=self)
        dialogo.exec()

        if dialogo.conciliado:
            self.carregar()

    def ignorar(self):

        transacao = self._transacao_selecionada()
        if transacao is None:
            return

        resposta = QMessageBox.question(
            self, "Ignorar transação",
            "Ignorar essa transação? Ela não vai mais aparecer nas "
            "pendentes.",
        )
        if resposta != QMessageBox.Yes:
            return

        rodar_em_thread(
            self,
            ignorar_transacao,
            transacao["id"],
            ao_sucesso=self._ao_mutacao_sucesso,
            ao_erro=self._ao_importar_erro,
        )

    def desconciliar(self):

        transacao = self._transacao_selecionada()
        if transacao is None:
            return

        resposta = QMessageBox.question(
            self, "Desconciliar",
            "Desfazer a conciliação dessa transação?",
        )
        if resposta != QMessageBox.Yes:
            return

        rodar_em_thread(
            self,
            desconciliar_transacao,
            transacao["id"],
            ao_sucesso=self._ao_mutacao_sucesso,
            ao_erro=self._ao_importar_erro,
        )

    def _ao_mutacao_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            self._exibir_erro(response)

    def _exibir_erro(self, response):
        try:
            erro = response.json().get("detail") or str(response.json())
        except Exception:
            erro = response.text
        QMessageBox.critical(self, "Erro", str(erro))
