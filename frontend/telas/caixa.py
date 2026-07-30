from telas.suprimento import SuprimentoWindow
from telas.sangria import SangriaWindow
from telas.abrir_caixa import AbrirCaixaWindow
from telas.fechar_caixa import FecharCaixaWindow

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QDialog,
    QMessageBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from services.caixa_service import (
    caixa_aberto,
    abrir_caixa,
    resumo_caixa,
    listar_movimentos_caixa,
)

from services.movimento_caixa_service import (
    criar_sangria,
    criar_suprimento,
)

from design import tokens
from design.icons import icone_pixmap
from design.widgets import BotaoSecundario, CardKPI


class Caixa(QWidget):

    def __init__(self):
        super().__init__()

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self.paginas = QStackedWidget()
        raiz.addWidget(self.paginas)

        self.pagina_sem_caixa = self._criar_pagina_sem_caixa()
        self.pagina_com_caixa = self._criar_pagina_com_caixa()

        self.paginas.addWidget(self.pagina_sem_caixa)
        self.paginas.addWidget(self.pagina_com_caixa)

        self.carregar()

    # ======================================
    # PÁGINA · SEM CAIXA ABERTO
    # ======================================

    def _criar_pagina_sem_caixa(self):

        pagina = QWidget()

        layout = QVBoxLayout(pagina)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        icone = QLabel()
        icone.setAlignment(Qt.AlignCenter)
        icone.setFixedSize(72, 72)
        icone.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA};
            border-radius:36px;
        """)
        icone.setPixmap(icone_pixmap("lock", cor=tokens.PRIMARIA, tamanho=30))

        titulo = QLabel("Nenhum caixa aberto")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_XL}px; font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            "Abra o caixa para liberar o Frente de Caixa e "
            "começar a registrar vendas."
        )
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_SM}px; color:{tokens.TEXTO_SECUNDARIO};
        """)
        subtitulo.setFixedWidth(360)

        bt_abrir = QPushButton("Abrir Caixa")
        bt_abrir.setCursor(Qt.PointingHandCursor)
        bt_abrir.setFixedWidth(200)
        bt_abrir.setMinimumHeight(46)
        bt_abrir.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.SECUNDARIA}; color:white;
                font-weight:700; border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.SECUNDARIA_HOVER}; }}
        """)
        bt_abrir.clicked.connect(self.abrir_caixa)

        layout.addWidget(icone, alignment=Qt.AlignHCenter)
        layout.addWidget(titulo)
        layout.addWidget(subtitulo, alignment=Qt.AlignHCenter)
        layout.addSpacing(8)
        layout.addWidget(bt_abrir, alignment=Qt.AlignHCenter)

        return pagina

    # ======================================
    # PÁGINA · CAIXA ABERTO
    # ======================================

    def _criar_pagina_com_caixa(self):

        pagina = QWidget()

        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        # ---- cabeçalho de status ----

        status_frame = QFrame()
        status_frame.setStyleSheet(f"""
            QFrame {{
                background:{tokens.SIDEBAR};
                border-radius:{tokens.RADIUS_MD}px;
            }}
        """)

        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(24, 18, 24, 18)

        col_status = QVBoxLayout()
        col_status.setSpacing(4)

        linha_status = QHBoxLayout()
        linha_status.setSpacing(8)

        bolinha = QLabel()
        bolinha.setFixedSize(10, 10)
        bolinha.setStyleSheet(f"background:{tokens.SUCESSO}; border-radius:5px;")

        self.lbl_status = QLabel("CAIXA ABERTO")
        self.lbl_status.setStyleSheet(f"""
            background:transparent; color:white;
            font-size:{tokens.TAMANHO_LG}px; font-weight:800;
        """)

        linha_status.addWidget(bolinha)
        linha_status.addWidget(self.lbl_status)
        linha_status.addStretch()

        self.lbl_abertura = QLabel("Aberto em --")
        self.lbl_abertura.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_status.addLayout(linha_status)
        col_status.addWidget(self.lbl_abertura)

        status_layout.addLayout(col_status)
        status_layout.addStretch()

        col_total = QVBoxLayout()
        col_total.setSpacing(2)

        lbl_total_titulo = QLabel("TOTAL PREVISTO NA GAVETA")
        lbl_total_titulo.setAlignment(Qt.AlignRight)
        lbl_total_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        self.lbl_total_previsto = QLabel("R$ 0,00")
        self.lbl_total_previsto.setAlignment(Qt.AlignRight)
        self.lbl_total_previsto.setStyleSheet(f"""
            background:transparent; color:white;
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)

        col_total.addWidget(lbl_total_titulo)
        col_total.addWidget(self.lbl_total_previsto)

        status_layout.addLayout(col_total)

        layout.addWidget(status_frame)

        # ---- cards de resumo ----

        cards_layout = QGridLayout()
        cards_layout.setSpacing(14)

        self.card_troco = CardKPI("Troco inicial", "wallet", tokens.PRIMARIA)
        self.card_dinheiro = CardKPI("Vendas em dinheiro", "dollar-sign", tokens.SECUNDARIA)
        self.card_pix = CardKPI("Vendas PIX", "credit-card", tokens.PRIMARIA)
        self.card_cartao = CardKPI("Vendas cartão", "credit-card", tokens.PRIMARIA)
        self.card_suprimentos = CardKPI("Suprimentos", "arrow-up", tokens.SECUNDARIA)
        self.card_sangrias = CardKPI("Sangrias", "arrow-down", tokens.ERRO)
        self.card_prazo = CardKPI("Vendas a prazo", "file-text", tokens.TEXTO_SECUNDARIO)
        self.card_recebimentos_fiado = CardKPI(
            "Recebimentos fiado", "check", tokens.SECUNDARIA
        )
        self.card_total_geral = CardKPI("Total geral do turno", "trending-up", tokens.PRIMARIA)

        cards_layout.addWidget(self.card_troco, 0, 0)
        cards_layout.addWidget(self.card_dinheiro, 0, 1)
        cards_layout.addWidget(self.card_pix, 0, 2)
        cards_layout.addWidget(self.card_cartao, 0, 3)
        cards_layout.addWidget(self.card_suprimentos, 1, 0)
        cards_layout.addWidget(self.card_sangrias, 1, 1)
        cards_layout.addWidget(self.card_prazo, 1, 2)
        cards_layout.addWidget(self.card_recebimentos_fiado, 1, 3)
        cards_layout.addWidget(self.card_total_geral, 2, 0)

        for coluna in range(4):
            cards_layout.setColumnStretch(coluna, 1)

        layout.addLayout(cards_layout)

        # ---- ações ----

        acoes_layout = QHBoxLayout()
        acoes_layout.setSpacing(10)

        self.bt_suprimento = QPushButton("+ Suprimento")
        self.bt_suprimento.setCursor(Qt.PointingHandCursor)
        self.bt_suprimento.setMinimumHeight(46)
        self.bt_suprimento.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; color:{tokens.SECUNDARIA_HOVER};
                border:1.5px solid {tokens.SECUNDARIA}; border-radius:{tokens.RADIUS_SM}px;
                font-weight:700; padding:0 18px;
            }}
            QPushButton:hover {{ background:{tokens.SUCESSO_CLARO}; }}
        """)
        self.bt_suprimento.clicked.connect(self.suprimento)

        self.bt_sangria = QPushButton("- Sangria")
        self.bt_sangria.setCursor(Qt.PointingHandCursor)
        self.bt_sangria.setMinimumHeight(46)
        self.bt_sangria.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; color:{tokens.ERRO};
                border:1.5px solid {tokens.ERRO}; border-radius:{tokens.RADIUS_SM}px;
                font-weight:700; padding:0 18px;
            }}
            QPushButton:hover {{ background:{tokens.ERRO_CLARO}; }}
        """)
        self.bt_sangria.clicked.connect(self.sangria)

        self.bt_encerrar = QPushButton("Encerrar Caixa")
        self.bt_encerrar.setCursor(Qt.PointingHandCursor)
        self.bt_encerrar.setMinimumHeight(46)
        self.bt_encerrar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.SIDEBAR}; color:white;
                border-radius:{tokens.RADIUS_SM}px; padding:0 22px; font-weight:700;
            }}
            QPushButton:hover {{ background:{tokens.SIDEBAR_HOVER}; }}
        """)
        self.bt_encerrar.clicked.connect(self.fechar_caixa)

        acoes_layout.addWidget(self.bt_suprimento)
        acoes_layout.addWidget(self.bt_sangria)
        acoes_layout.addStretch()
        acoes_layout.addWidget(self.bt_encerrar)

        layout.addLayout(acoes_layout)

        # ---- histórico de movimentações ----

        historico_cabecalho = QHBoxLayout()

        lbl_historico_titulo = QLabel("HISTÓRICO DO CAIXA")
        lbl_historico_titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_XS}px; font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.bt_atualizar_historico = BotaoSecundario("Atualizar", icone_nome="refresh-cw")
        self.bt_atualizar_historico.setMinimumHeight(32)
        self.bt_atualizar_historico.clicked.connect(self.carregar)

        historico_cabecalho.addWidget(lbl_historico_titulo)
        historico_cabecalho.addStretch()
        historico_cabecalho.addWidget(self.bt_atualizar_historico)

        layout.addLayout(historico_cabecalho)

        self.tabela_movimentos = QTableWidget()
        self.tabela_movimentos.setColumnCount(4)
        self.tabela_movimentos.setHorizontalHeaderLabels(
            ["Data/Hora", "Tipo", "Valor", "Descrição"]
        )
        self.tabela_movimentos.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela_movimentos.verticalHeader().setVisible(False)
        self.tabela_movimentos.setAlternatingRowColors(True)
        self.tabela_movimentos.setEditTriggers(
            QTableWidget.NoEditTriggers
        )
        self.tabela_movimentos.setSelectionMode(
            QTableWidget.NoSelection
        )
        self.tabela_movimentos.setFocusPolicy(Qt.NoFocus)
        self.tabela_movimentos.setStyleSheet(f"""
            QTableWidget {{
                background:{tokens.CARD};
                alternate-background-color:{tokens.FUNDO};
                border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_MD}px;
                gridline-color:{tokens.BORDA};
                color:{tokens.TEXTO};
                font-size:{tokens.TAMANHO_BASE}px;
            }}
            QTableWidget::item {{
                color:{tokens.TEXTO};
                background:transparent;
            }}
            QHeaderView::section {{
                background:{tokens.FUNDO};
                color:{tokens.TEXTO_SECUNDARIO};
                padding:8px;
                border:none;
                border-bottom:1px solid {tokens.BORDA};
                font-weight:700;
                font-size:{tokens.TAMANHO_XS}px;
            }}
        """)

        layout.addWidget(self.tabela_movimentos, stretch=1)

        return pagina

    # ======================================
    # CARREGAR DADOS
    # ======================================

    def carregar(self):

        caixa = caixa_aberto()

        if caixa is None:
            self.paginas.setCurrentWidget(self.pagina_sem_caixa)
            return

        resumo = resumo_caixa() or {}

        data_abertura = str(caixa.get("data_abertura", ""))[:16]
        data_abertura = data_abertura.replace("T", " ")

        self.lbl_abertura.setText(f"Aberto em {data_abertura}")

        total_previsto = float(resumo.get("total_previsto", 0) or 0)
        self.lbl_total_previsto.setText(f"R$ {total_previsto:.2f}")

        self.card_troco.definir_valor(
            f"R$ {float(resumo.get('saldo_inicial', 0) or 0):.2f}"
        )
        self.card_dinheiro.definir_valor(
            f"R$ {float(resumo.get('vendas_dinheiro', 0) or 0):.2f}"
        )
        self.card_pix.definir_valor(
            f"R$ {float(resumo.get('vendas_pix', 0) or 0):.2f}"
        )
        self.card_cartao.definir_valor(
            f"R$ {float(resumo.get('vendas_cartao', 0) or 0):.2f}"
        )
        self.card_suprimentos.definir_valor(
            f"+ R$ {float(resumo.get('suprimentos', 0) or 0):.2f}"
        )
        self.card_sangrias.definir_valor(
            f"- R$ {float(resumo.get('sangrias', 0) or 0):.2f}"
        )
        self.card_prazo.definir_valor(
            f"R$ {float(resumo.get('vendas_prazo', 0) or 0):.2f}"
        )
        self.card_recebimentos_fiado.definir_valor(
            f"R$ {float(resumo.get('recebimentos_fiado', 0) or 0):.2f}"
        )
        self.card_total_geral.definir_valor(
            f"R$ {float(resumo.get('total_geral', 0) or 0):.2f}"
        )

        self.carregar_movimentos(caixa["id"])

        self.paginas.setCurrentWidget(self.pagina_com_caixa)

    def carregar_movimentos(self, caixa_id):

        movimentos = listar_movimentos_caixa(caixa_id)

        movimentos = sorted(
            movimentos,
            key=lambda m: m.get("data", ""),
            reverse=True,
        )

        self.tabela_movimentos.setRowCount(len(movimentos))

        for linha, mov in enumerate(movimentos):

            data = str(mov.get("data", ""))
            if "T" in data:
                data = data.replace("T", " ")

            self.tabela_movimentos.setItem(
                linha, 0, QTableWidgetItem(data[:19])
            )
            self.tabela_movimentos.setItem(
                linha, 1, QTableWidgetItem(mov.get("tipo", ""))
            )
            self.tabela_movimentos.setItem(
                linha,
                2,
                QTableWidgetItem(
                    f"R$ {float(mov.get('valor', 0) or 0):.2f}"
                ),
            )
            self.tabela_movimentos.setItem(
                linha,
                3,
                QTableWidgetItem(mov.get("descricao") or ""),
            )

    # ======================================
    # AÇÕES
    # ======================================

    def abrir_caixa(self):

        janela = AbrirCaixaWindow()

        if janela.exec() != QDialog.Accepted:
            return

        response = abrir_caixa(janela.saldo)

        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.warning(self, "Erro", erro)

    def fechar_caixa(self):

        janela = FecharCaixaWindow()

        if janela.exec() != QDialog.Accepted:
            return

        QMessageBox.information(
            self,
            "Sucesso",
            "Caixa fechado com sucesso!",
        )

        self.carregar()

    def sangria(self):

        janela = SangriaWindow()

        if janela.exec() != QDialog.Accepted:
            return

        dados = janela.dados

        response = criar_sangria(
            dados["valor"],
            dados["descricao"],
        )

        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", erro)

    def suprimento(self):

        janela = SuprimentoWindow()

        if janela.exec() != QDialog.Accepted:
            return

        dados = janela.dados

        response = criar_suprimento(
            dados["valor"],
            dados["descricao"],
        )

        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", erro)
