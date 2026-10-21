from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
)

from services.relatorio_service import mes_a_mes
from services.worker import rodar_em_thread
from design import tokens
from utils.formatacao import formatar_moeda

_MESES_CURTOS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# (rotulo, chave do backend, como somar na coluna Total)
LINHAS = [
    ("Faturamento", "faturamento", "soma"),
    ("Nº de vendas", "quantidade_vendas", "soma"),
    ("Ticket médio", "ticket_medio", "media"),
    ("Lucro bruto", "lucro", "soma"),
    ("Entrou no caixa", "entrou", "soma"),
    ("Vendido no fiado", "vendido_fiado", "soma"),
    ("Fiado recebido", "fiado_recebido", "soma"),
    ("Contas pagas", "contas_pagas", "soma"),
    ("Sangrias e retiradas", "sangrias", "soma"),
    ("Sobrou", "sobrou", "soma"),
]


def montar_quadro(meses):
    """[(rotulo, [texto por mes] + [texto do total])] -- separado da
    tabela pra testar sem Qt."""
    linhas = []
    for rotulo, chave, total in LINHAS:
        valores = [float(m.get(chave) or 0) for m in meses]
        if chave == "lucro" and any(m.get("custo_incompleto") for m in meses):
            # produto sem custo cadastrado: lucro seria inventado
            textos = ["—" if m.get("custo_incompleto") else formatar_moeda(v) for m, v in zip(meses, valores)]
            textos.append("—")
        elif chave == "quantidade_vendas":
            textos = [str(int(v)) for v in valores] + [str(int(sum(valores)))]
        else:
            if total == "media":
                vendas = sum(float(m.get("quantidade_vendas") or 0) for m in meses)
                fat = sum(float(m.get("faturamento") or 0) for m in meses)
                tot = fat / vendas if vendas else 0
            else:
                tot = sum(valores)
            textos = [formatar_moeda(v) for v in valores + [tot]]
        linhas.append((rotulo, textos))
    return linhas


class MesAMesMixin:
    """Aba Mes a mes: o ano inteiro, um mes por coluna."""

    def _criar_pagina_mes_a_mes(self):

        pagina, layout = self._pagina_rolavel(espacamento=12)

        cabecalho = QHBoxLayout()
        titulo = QLabel("Mês a mês")
        titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_LG}px; font-weight:700; color:{tokens.TEXTO};
            background:transparent;
        """)
        cabecalho.addWidget(titulo)
        cabecalho.addStretch()

        estilo_combo = f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:0 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """
        self.combo_ano_mes = QComboBox()
        ano = date.today().year
        for a in range(ano, ano - 3, -1):
            self.combo_ano_mes.addItem(str(a), a)
        self.combo_ano_mes.setMinimumHeight(34)
        self.combo_ano_mes.setCursor(Qt.PointingHandCursor)
        self.combo_ano_mes.setStyleSheet(estilo_combo)
        self.combo_ano_mes.currentIndexChanged.connect(self._atualizar_mes_a_mes)
        cabecalho.addWidget(self.combo_ano_mes)

        self.combo_loja_mes = QComboBox()
        self.combo_loja_mes.setMinimumHeight(34)
        self.combo_loja_mes.setCursor(Qt.PointingHandCursor)
        self.combo_loja_mes.setStyleSheet(estilo_combo)
        self._carregar_combo_lojas(self.combo_loja_mes)
        self.combo_loja_mes.currentIndexChanged.connect(self._atualizar_mes_a_mes)
        cabecalho.addWidget(self.combo_loja_mes)

        layout.addLayout(cabecalho)

        self.tabela_mes_a_mes = QTableWidget()
        self._estilizar_tabela(self.tabela_mes_a_mes)
        self.tabela_mes_a_mes.setSelectionMode(QTableWidget.NoSelection)
        self.tabela_mes_a_mes.verticalHeader().setVisible(False)
        self.tabela_mes_a_mes.setWordWrap(False)
        self.tabela_mes_a_mes.setMinimumHeight(44 * (len(LINHAS) + 1) + 8)
        layout.addWidget(self.tabela_mes_a_mes)

        self.lbl_mes_a_mes_nota = QLabel(
            "Faturamento e lucro: as mesmas contas da aba Financeiro. "
            "Entrou, contas pagas, sangrias e sobrou: as mesmas da aba Caixa "
            "(só o que foi lançado no sistema). Lucro “—” = produto sem custo cadastrado."
        )
        self.lbl_mes_a_mes_nota.setWordWrap(True)
        self.lbl_mes_a_mes_nota.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SECUNDARIO}; font-size:{tokens.TAMANHO_SM}px;"
        )
        layout.addWidget(self.lbl_mes_a_mes_nota)
        layout.addStretch()

        self._mes_a_mes_carregado = False
        return pagina

    def _atualizar_mes_a_mes(self):
        self._mes_a_mes_carregado = True
        rodar_em_thread(
            self, mes_a_mes, self.combo_ano_mes.currentData(), self.combo_loja_mes.currentData(),
            ao_sucesso=self._preencher_mes_a_mes,
            ao_erro=self._ao_erro_mes_a_mes,
        )

    def _ao_erro_mes_a_mes(self, erro):
        self.lbl_mes_a_mes_nota.setText(str(erro))

    def _preencher_mes_a_mes(self, meses):
        tabela = self.tabela_mes_a_mes
        cabecalhos = [""] + [_MESES_CURTOS[m["mes"] - 1] for m in meses] + ["Total"]
        tabela.setColumnCount(len(cabecalhos))
        tabela.setHorizontalHeaderLabels(cabecalhos)
        tabela.setRowCount(0)
        tabela.setRowCount(len(LINHAS))
        negrito = QFont()
        negrito.setBold(True)
        for linha, (rotulo, textos) in enumerate(montar_quadro(meses)):
            item = QTableWidgetItem(rotulo)
            item.setFont(negrito)
            tabela.setItem(linha, 0, item)
            for coluna, texto in enumerate(textos, start=1):
                celula = QTableWidgetItem(texto)
                ultima = coluna == len(textos)
                if rotulo == "Sobrou" or ultima:
                    celula.setFont(negrito)
                if rotulo == "Sobrou" and "-" in texto:
                    celula.setForeground(QColor(tokens.ERRO))
                tabela.setItem(linha, coluna, celula)
        # 12 meses + total: cada coluna do tamanho do valor, sem quebrar
        # o "R$ 1.008,54" em duas linhas; se nao couber, rola de lado
        tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
