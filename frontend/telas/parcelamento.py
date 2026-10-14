import re
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidgetItem, QToolTip,
    QWidget,
)

from design import tokens
from design.icons import icone
from design.widgets import (
    BotaoPerigo, BotaoSecundario, CardKPI, DialogoPadrao, pedir_texto,
)
from services.conta_pagar_service import (
    atualizar_conta_pagar,
    cancelar_parcelas_restantes,
    ler_boleto,
    listar_parcelamento,
)
from services.worker import rodar_em_thread
from utils.formatacao import formatar_moeda
from widgets.tables.standard_table import StandardTable

_SITUACAO = {"PAGO": "Paga", "PENDENTE": "Em aberto", "CANCELADO": "Cancelada"}


def copiar_codigo_boleto(numero_boleto):
    """Copia so' os numeros do boleto -- o app do banco aceita colar assim."""

    codigo = re.sub(r"\D", "", numero_boleto or "")
    if not codigo:
        return
    QGuiApplication.clipboard().setText(codigo)
    QToolTip.showText(QCursor.pos(), "Código copiado! Cole no app do banco.")


def _erro_da_resposta(response):
    try:
        return response.json().get("detail") or response.text
    except Exception:
        return response.text


class ParcelamentoDialog(DialogoPadrao):
    """Todas as parcelas de um boleto parcelado juntas: quanto já foi
    pago, quanto falta, e cancelar as que faltam de uma vez (acordo com
    o fornecedor, compra devolvida). Cada parcela tem o seu boleto: a
    coluna Código copia o que já foi bipado ou deixa bipar o que falta."""

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

        self.tabela = StandardTable(["Parcela", "Vencimento", "Valor", "Situação", "Código do boleto"])
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
            self.tabela.setCellWidget(linha, 4, self._celula_codigo(parcela))

        validas = [p for p in parcelas if p["status"] != "CANCELADO"]
        pagas = [p for p in parcelas if p["status"] == "PAGO"]
        pendentes = [p for p in parcelas if p["status"] == "PENDENTE"]

        self.card_total.definir_valor(formatar_moeda(sum(float(p["valor"]) for p in validas)))
        self.card_pago.definir_valor(formatar_moeda(sum(float(p["valor"]) for p in pagas)))
        self.card_falta.definir_valor(formatar_moeda(sum(float(p["valor"]) for p in pendentes)))
        self.lbl_resumo.setText(
            f"{len(pagas)} de {len(validas)} parcela(s) paga(s) · "
            f"{len(pendentes)} em aberto"
        )
        self.bt_cancelar_restantes.setEnabled(bool(pendentes))

    def _celula_codigo(self, parcela):

        celula = QWidget()
        celula.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(celula)
        lay.setContentsMargins(6, 2, 6, 2)

        if parcela.get("numero_boleto"):
            botao = QPushButton(" Copiar")
            botao.setIcon(icone("copy", cor=tokens.PRIMARIA, tamanho=14))
            botao.setToolTip(parcela["numero_boleto"])
            botao.clicked.connect(lambda: copiar_codigo_boleto(parcela["numero_boleto"]))
        elif parcela["status"] == "PENDENTE":
            botao = QPushButton(" Bipar código")
            botao.setIcon(icone("plus", cor=tokens.PRIMARIA, tamanho=14))
            botao.setToolTip("Bipe ou digite o código do boleto dessa parcela")
            botao.clicked.connect(lambda: self.bipar_codigo(parcela))
        else:
            lay.addWidget(QLabel("—"))
            return celula

        botao.setCursor(Qt.PointingHandCursor)
        botao.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; color:{tokens.PRIMARIA};
                font-weight:600; text-align:left; padding:2px 4px;
            }}
            QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA}; border-radius:6px; }}
        """)
        lay.addWidget(botao)
        lay.addStretch()
        return celula

    def bipar_codigo(self, parcela):

        numero = f"{parcela.get('parcela_numero')}/{parcela.get('parcela_total')}"
        texto, ok = pedir_texto(
            self, f"Boleto da parcela {numero}", "Código de barras ou linha digitável",
            icone_nome="file-text", subtitulo="Bipe o boleto dessa parcela",
            texto_botao="Guardar",
        )
        if not ok or not re.sub(r"\D", "", texto):
            return

        response = ler_boleto(codigo=re.sub(r"\D", "", texto))
        if response.status_code != 200:
            QMessageBox.warning(self, "Boleto", _erro_da_resposta(response))
            return
        lido = response.json()

        repetido = lido.get("ja_lancado")
        if repetido and repetido["id"] != parcela["id"]:
            QMessageBox.warning(
                self, "Boleto já lançado",
                f"Esse boleto já está na conta {repetido.get('descricao') or 'Despesa'}. "
                "Confira se bipou o boleto certo.",
            )
            return

        payload = {"numero_boleto": lido.get("linha_digitavel") or texto.strip()}
        if lido.get("vencimento"):
            payload["data_vencimento"] = f"{lido['vencimento']}T00:00:00"

        valor_boleto = lido.get("valor")
        if valor_boleto is not None and abs(float(valor_boleto) - float(parcela["valor"])) > 0.005:
            resposta = QMessageBox.question(
                self, "Valor diferente",
                f"O boleto é de {formatar_moeda(float(valor_boleto))}, mas a parcela "
                f"{numero} é de {formatar_moeda(float(parcela['valor']))}.\n\n"
                "Guardar mesmo assim? O valor da parcela passa a ser o do boleto.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if resposta != QMessageBox.Yes:
                return
            payload["valor"] = str(valor_boleto)

        response = atualizar_conta_pagar(parcela["id"], payload)
        if response.status_code != 200:
            QMessageBox.warning(self, "Boleto", _erro_da_resposta(response))
            return

        self.alterou = True
        self.carregar()

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
            QMessageBox.warning(self, "Cancelar parcelas", _erro_da_resposta(response))
            return

        self.alterou = True
        self.carregar()
