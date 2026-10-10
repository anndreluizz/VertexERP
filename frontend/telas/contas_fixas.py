from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
)

from design import tokens
from design.widgets import BotaoPerigo, BotaoSecundario, DialogoPadrao
from services.conta_pagar_service import (
    atualizar_conta_fixa,
    listar_contas_fixas,
    parar_conta_fixa,
)
from services.worker import rodar_em_thread
from utils.formatacao import formatar_moeda
from widgets.tables.standard_table import StandardTable


_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _ate(fim_competencia):
    if not fim_competencia:
        return "Sempre"
    ano, mes, _dia = fim_competencia.split("-")
    return f"{_MESES[int(mes) - 1]}/{ano}"


def _erro(response):
    try:
        return response.json().get("detail") or response.text
    except Exception:
        return response.text


class ContasFixasDialog(DialogoPadrao):
    """Contas que se repetem todo mês (luz, funcionária, aluguel). Pra
    criar uma, é na Nova despesa → "Todo mês". Aqui só muda o valor dos
    próximos meses ou para de repetir -- as contas já criadas continuam
    em Contas a Pagar."""

    def __init__(self, parent=None):

        super().__init__(
            "Contas fixas",
            "Contas que se repetem todo mês. O sistema cria a de cada mês sozinho.",
            "refresh-cw", tokens.PRIMARIA, tokens.PRIMARIA_CLARA,
            largura=DialogoPadrao.GRANDE, parent=parent,
        )

        self.fixas = []

        ajuda = QLabel(
            "Para cadastrar uma conta fixa: Nova despesa → Repetição: Todo mês."
        )
        ajuda.setWordWrap(True)
        ajuda.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        self.corpo.addWidget(ajuda)

        self.tabela = StandardTable(["Conta", "Vence todo dia", "Valor", "Tipo", "Até"])
        self.tabela.setMinimumHeight(260)
        self.tabela.itemSelectionChanged.connect(self._atualizar_botoes)
        self.corpo.addWidget(self.tabela, stretch=1)

        acoes = QHBoxLayout()
        self.bt_valor = BotaoSecundario("Mudar valor")
        self.bt_valor.setToolTip("Muda o valor dos próximos meses")
        self.bt_valor.clicked.connect(self.mudar_valor)
        self.bt_parar = BotaoPerigo("Parar de repetir")
        self.bt_parar.clicked.connect(self.parar)
        acoes.addWidget(self.bt_valor)
        acoes.addStretch()
        acoes.addWidget(self.bt_parar)
        self.corpo.addLayout(acoes)

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.clicked.connect(self.accept)
        self.definir_botoes(bt_fechar).setVisible(False)

        self._atualizar_botoes()
        self.ajustar_altura()
        self.carregar()

    def carregar(self):
        rodar_em_thread(
            self,
            listar_contas_fixas,
            ao_sucesso=self._ao_carregar,
            ao_erro=self._ao_carregar_erro,
        )

    def _ao_carregar(self, fixas):

        self.fixas = fixas
        self.tabela.setRowCount(len(fixas))

        for linha, fixa in enumerate(fixas):
            valores = [
                fixa["descricao"],
                str(fixa["dia_vencimento"]),
                formatar_moeda(float(fixa["valor"])),
                "Muda todo mês" if fixa["valor_variavel"] else "Valor fixo",
                _ate(fixa.get("fim_competencia")),
            ]
            for coluna, texto in enumerate(valores):
                item = QTableWidgetItem(texto)
                item.setData(Qt.UserRole, fixa["id"])
                self.tabela.setItem(linha, coluna, item)

        self._atualizar_botoes()

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _selecionada(self):
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return None
        return self.fixas[linhas[0].row()]

    def _atualizar_botoes(self):
        tem = self._selecionada() is not None
        self.bt_valor.setEnabled(tem)
        self.bt_parar.setEnabled(tem)

    def mudar_valor(self):

        fixa = self._selecionada()
        if fixa is None:
            return

        valor, ok = QInputDialog.getDouble(
            self,
            "Mudar valor",
            f"Novo valor de \"{fixa['descricao']}\" a partir do próximo mês:",
            float(fixa["valor"]), 0.01, 10_000_000, 2,
        )
        if not ok:
            return

        response = atualizar_conta_fixa(fixa["id"], {"valor": round(valor, 2)})
        if response.status_code != 200:
            QMessageBox.warning(self, "Mudar valor", _erro(response))
            return

        self.carregar()

    def parar(self):

        fixa = self._selecionada()
        if fixa is None:
            return

        resposta = QMessageBox.question(
            self,
            "Parar de repetir",
            f"\"{fixa['descricao']}\" não vai mais ser criada nos próximos "
            "meses. As contas que já estão em Contas a Pagar continuam lá.\n\n"
            "Parar de repetir?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        response = parar_conta_fixa(fixa["id"])
        if response.status_code != 200:
            QMessageBox.warning(self, "Parar de repetir", _erro(response))
            return

        self.carregar()
