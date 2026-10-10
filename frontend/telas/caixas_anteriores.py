"""Caixas anteriores: lista os caixas já fechados e, ao escolher um,
mostra o que foi vendido e o que foi recebido naquele turno, com o
resumo e o botão de reimprimir o fechamento (mesmo extrato impresso ao
fechar -- ver telas/fechar_caixa.py)."""

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox, QTableWidgetItem, QVBoxLayout,
)

from design import tokens
from design.widgets import BotaoPrimario, BotaoSecundario
from services import api
from services.caixa_service import historico_caixa, listar_movimentos_caixa, resumo_caixa_por_id
from services.worker import em_paralelo, rodar_em_thread
from telas.fechar_caixa import imprimir_fechamento
from utils.formatacao import formatar_moeda, nome_forma
from widgets.tables.standard_table import StandardTable

_ROTULOS = {
    "RECEBIMENTO_FIADO": "Recebimento de fiado",
    "SUPRIMENTO": "Suprimento",
    "SANGRIA": "Sangria",
    "ESTORNO": "Estorno",
    "VENDA": "Venda",
}


def _data(texto, formato="%d/%m/%Y %H:%M"):
    if not texto:
        return "—"
    return datetime.fromisoformat(str(texto)[:19]).strftime(formato)


def _detalhe_do_caixa(caixa_id):
    """Worker thread: resumo + movimentos do caixa escolhido."""
    resumo, movimentos = em_paralelo(
        (resumo_caixa_por_id, caixa_id), (listar_movimentos_caixa, caixa_id),
    )
    return caixa_id, resumo or {}, sorted(movimentos or [], key=lambda m: m.get("data", ""))


def separar_movimentos(movimentos):
    """(vendas, recebimentos e outros) -- vendas = VENDA/ESTORNO; o resto
    é o que entrou ou saiu da gaveta sem ser venda."""
    vendas = [m for m in movimentos if m.get("tipo") in ("VENDA", "ESTORNO")]
    outros = [m for m in movimentos if m.get("tipo") not in ("VENDA", "ESTORNO")]
    return vendas, outros


def _titulo(texto):
    lbl = QLabel(texto)
    lbl.setStyleSheet(
        f"background:transparent; font-size:{tokens.TAMANHO_MD}px;"
        f" font-weight:700; color:{tokens.TEXTO};"
    )
    return lbl


class CaixasAnterioresDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Caixas anteriores")
        self.setStyleSheet(f"background:{tokens.FUNDO};")
        self.resize(1200, 720)

        self.caixas = []
        self.caixa_atual = None
        self.resumo = {}
        self.movimentos = []

        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(20, 20, 20, 20)
        raiz.setSpacing(18)

        # ---- esquerda: lista de caixas
        esquerda = QVBoxLayout()
        esquerda.addWidget(_titulo("Caixas fechados"))
        self.tabela_caixas = StandardTable(["Data", "Operador", "Fechado às", "Na gaveta"])
        self.tabela_caixas.itemSelectionChanged.connect(self._ao_escolher_caixa)
        esquerda.addWidget(self.tabela_caixas, 1)
        self.tabela_caixas.setMinimumWidth(400)
        raiz.addLayout(esquerda, 5)

        # ---- direita: detalhe do caixa escolhido
        direita = QVBoxLayout()
        direita.setSpacing(10)

        topo = QHBoxLayout()
        self.lbl_caixa = _titulo("Escolha um caixa na lista")
        topo.addWidget(self.lbl_caixa)
        topo.addStretch()
        self.bt_imprimir = BotaoPrimario("Reimprimir fechamento", icone_nome="printer")
        self.bt_imprimir.setEnabled(False)
        self.bt_imprimir.clicked.connect(self.reimprimir)
        topo.addWidget(self.bt_imprimir)
        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.clicked.connect(self.reject)
        topo.addWidget(bt_fechar)
        direita.addLayout(topo)

        self.lbl_resumo = QLabel()
        self.lbl_resumo.setWordWrap(True)
        self.lbl_resumo.setStyleSheet(
            f"background:{tokens.CARD}; border:1px solid {tokens.BORDA};"
            f" border-radius:{tokens.RADIUS_MD}px; padding:10px;"
            f" color:{tokens.TEXTO}; font-size:{tokens.TAMANHO_SM}px;"
        )
        self.lbl_resumo.setVisible(False)
        direita.addWidget(self.lbl_resumo)

        self.lbl_vendas = _titulo("Vendas")
        direita.addWidget(self.lbl_vendas)
        self.tabela_vendas = StandardTable(["Hora", "Venda", "Pagamento", "Valor"])
        direita.addWidget(self.tabela_vendas, 3)

        self.lbl_recebimentos = _titulo("Recebimentos, suprimentos e sangrias")
        direita.addWidget(self.lbl_recebimentos)
        self.tabela_recebimentos = StandardTable(["Hora", "Tipo", "Descrição", "Pagamento", "Valor"])
        direita.addWidget(self.tabela_recebimentos, 2)

        raiz.addLayout(direita, 7)

        rodar_em_thread(self, historico_caixa, None, 90, ao_sucesso=self._ao_carregar_caixas)

    # ------------------------------------------------------------------

    def _ao_carregar_caixas(self, caixas):
        self.caixas = [c for c in caixas if c.get("status") == "FECHADO"]
        self.tabela_caixas.setRowCount(len(self.caixas))
        for linha, caixa in enumerate(self.caixas):
            for coluna, texto in enumerate([
                _data(caixa["data_abertura"], "%d/%m/%Y"),
                caixa.get("usuario_nome") or "—",
                _data(caixa.get("data_fechamento"), "%d/%m %H:%M"),
                formatar_moeda(caixa.get("saldo_final")),
            ]):
                self.tabela_caixas.setItem(linha, coluna, QTableWidgetItem(texto))
        if not self.caixas:
            self.lbl_caixa.setText("Nenhum caixa fechado ainda")

    def _ao_escolher_caixa(self):
        linha = self.tabela_caixas.currentRow()
        if linha < 0 or linha >= len(self.caixas):
            return
        self.caixa_atual = self.caixas[linha]
        self.bt_imprimir.setEnabled(False)
        self.lbl_caixa.setText(
            f"Caixa de {_data(self.caixa_atual['data_abertura'], '%d/%m/%Y')} · carregando..."
        )
        rodar_em_thread(
            self, _detalhe_do_caixa, self.caixa_atual["id"],
            ao_sucesso=self._ao_carregar_detalhe, ao_erro=self._ao_erro,
        )

    def _ao_erro(self, erro):
        QMessageBox.critical(self, "Caixas anteriores", str(erro))

    def _ao_carregar_detalhe(self, resultado):
        caixa_id, resumo, movimentos = resultado
        if not self.caixa_atual or caixa_id != self.caixa_atual["id"]:
            return  # a pessoa ja clicou em outro caixa

        self.resumo, self.movimentos = resumo, movimentos
        caixa = self.caixa_atual
        self.lbl_caixa.setText(
            f"Caixa de {_data(caixa['data_abertura'], '%d/%m/%Y')}"
            f" · {caixa.get('usuario_nome') or '—'}"
        )

        contado = caixa.get("valor_contado")
        self.lbl_resumo.setText(
            f"Aberto {_data(caixa['data_abertura'])} · fechado {_data(caixa.get('data_fechamento'))}\n"
            f"Troco inicial {formatar_moeda(resumo.get('saldo_inicial'))}  ·  "
            f"Dinheiro {formatar_moeda(resumo.get('vendas_dinheiro'))}  ·  "
            f"Pix {formatar_moeda(resumo.get('vendas_pix'))}  ·  "
            f"Cartão {formatar_moeda(resumo.get('vendas_cartao'))}  ·  "
            f"Fiado {formatar_moeda(resumo.get('vendas_prazo'))}\n"
            f"Recebido de fiado {formatar_moeda(resumo.get('recebimentos_fiado'))}  ·  "
            f"Suprimentos {formatar_moeda(resumo.get('suprimentos'))}  ·  "
            f"Sangrias {formatar_moeda(resumo.get('sangrias'))}\n"
            f"Previsto na gaveta {formatar_moeda(resumo.get('total_previsto'))}  ·  "
            f"Contado {formatar_moeda(contado) if contado is not None else 'não contado'}  ·  "
            f"Total geral do turno {formatar_moeda(resumo.get('total_geral'))}"
        )
        self.lbl_resumo.setVisible(True)

        vendas, outros = separar_movimentos(movimentos)
        total_vendas = sum(float(m.get("valor") or 0) for m in vendas)
        self.lbl_vendas.setText(f"Vendas ({len(vendas)}) · {formatar_moeda(total_vendas)}")
        self._preencher(self.tabela_vendas, [
            [_data(m.get("data"), "%H:%M"), m.get("descricao") or "",
             nome_forma(m.get("forma_pagamento")) or "", formatar_moeda(m.get("valor"))]
            for m in vendas
        ])

        recebido = sum(
            float(m.get("valor") or 0) for m in outros if m.get("tipo") == "RECEBIMENTO_FIADO"
        )
        self.lbl_recebimentos.setText(
            f"Recebimentos, suprimentos e sangrias · recebido de fiado {formatar_moeda(recebido)}"
        )
        self._preencher(self.tabela_recebimentos, [
            [_data(m.get("data"), "%H:%M"), _ROTULOS.get(m.get("tipo"), m.get("tipo") or ""),
             m.get("descricao") or "", nome_forma(m.get("forma_pagamento")) or "",
             ("- " if m.get("tipo") == "SANGRIA" else "") + formatar_moeda(m.get("valor"))]
            for m in outros
        ])

        self.bt_imprimir.setEnabled(True)

    @staticmethod
    def _preencher(tabela, linhas):
        tabela.setRowCount(len(linhas))
        for i, linha in enumerate(linhas):
            for j, texto in enumerate(linha):
                item = QTableWidgetItem(texto)
                if j == len(linha) - 1:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                tabela.setItem(i, j, item)

    def reimprimir(self):
        caixa = self.caixa_atual
        imprimir_fechamento(
            self, caixa, self.resumo, self.movimentos, caixa.get("valor_contado"),
            caixa.get("observacoes"), caixa.get("usuario_nome") or "—",
            caixa.get("data_fechamento"), api.configuracoes(),
        )
