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


class CardResumo(QFrame):

    def __init__(self, titulo, cor="#202225"):

        super().__init__()

        self.setStyleSheet("""
            QFrame {
                background:white;
                border:1px solid #e0e0e0;
                border-radius:10px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            "background:transparent; border:none; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        self.lbl_valor = QLabel("R$ 0,00")
        self.lbl_valor.setStyleSheet(
            f"background:transparent; border:none; font-size:20px; "
            f"font-weight:bold; color:{cor};"
        )

        layout.addWidget(lbl_titulo)
        layout.addWidget(self.lbl_valor)

    def atualizar(self, valor_texto):
        self.lbl_valor.setText(valor_texto)


class Caixa(QWidget):

    def __init__(self):
        super().__init__()

        self.setStyleSheet("background:#f4f5f7;")

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

        icone = QLabel("🔒")
        icone.setAlignment(Qt.AlignCenter)
        icone.setFixedSize(72, 72)
        icone.setStyleSheet("""
            background:#eef0f3;
            border-radius:36px;
            font-size:30px;
        """)

        titulo = QLabel("Nenhum caixa aberto")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(
            "font-size:18px; font-weight:bold; color:#202225;"
        )

        subtitulo = QLabel(
            "Abra o caixa para liberar o Frente de Caixa e "
            "começar a registrar vendas."
        )
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet("font-size:12px; color:gray;")
        subtitulo.setFixedWidth(360)

        bt_abrir = QPushButton("Abrir Caixa")
        bt_abrir.setFixedWidth(200)
        bt_abrir.setMinimumHeight(46)
        bt_abrir.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                font-weight:bold;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
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
        status_frame.setStyleSheet("""
            QFrame {
                background:#202225;
                border-radius:12px;
            }
        """)

        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(24, 18, 24, 18)

        col_status = QVBoxLayout()
        col_status.setSpacing(2)

        self.lbl_status = QLabel("🟢 CAIXA ABERTO")
        self.lbl_status.setStyleSheet(
            "background:transparent; color:white; "
            "font-size:16px; font-weight:bold;"
        )

        self.lbl_abertura = QLabel("Aberto em --")
        self.lbl_abertura.setStyleSheet(
            "background:transparent; color:#aaaaaa; font-size:11px;"
        )

        col_status.addWidget(self.lbl_status)
        col_status.addWidget(self.lbl_abertura)

        status_layout.addLayout(col_status)
        status_layout.addStretch()

        col_total = QVBoxLayout()
        col_total.setSpacing(2)

        lbl_total_titulo = QLabel("TOTAL PREVISTO NA GAVETA")
        lbl_total_titulo.setAlignment(Qt.AlignRight)
        lbl_total_titulo.setStyleSheet(
            "background:transparent; color:#aaaaaa; font-size:11px;"
        )

        self.lbl_total_previsto = QLabel("R$ 0,00")
        self.lbl_total_previsto.setAlignment(Qt.AlignRight)
        self.lbl_total_previsto.setStyleSheet(
            "background:transparent; color:white; "
            "font-size:22px; font-weight:bold;"
        )

        col_total.addWidget(lbl_total_titulo)
        col_total.addWidget(self.lbl_total_previsto)

        status_layout.addLayout(col_total)

        layout.addWidget(status_frame)

        # ---- cards de resumo ----

        cards_layout = QGridLayout()
        cards_layout.setSpacing(12)

        self.card_troco = CardResumo("Troco inicial")
        self.card_dinheiro = CardResumo("Vendas em dinheiro", "#2E7D32")
        self.card_pix = CardResumo("Vendas PIX", "#1565C0")
        self.card_cartao = CardResumo("Vendas cartão", "#1565C0")
        self.card_suprimentos = CardResumo("Suprimentos", "#2E7D32")
        self.card_sangrias = CardResumo("Sangrias", "#C62828")
        self.card_prazo = CardResumo("Vendas a prazo", "#757575")
        self.card_recebimentos_fiado = CardResumo(
            "Recebimentos fiado", "#2E7D32"
        )
        self.card_total_geral = CardResumo("Total geral do turno", "#1565C0")

        cards_layout.addWidget(self.card_troco, 0, 0)
        cards_layout.addWidget(self.card_dinheiro, 0, 1)
        cards_layout.addWidget(self.card_pix, 0, 2)
        cards_layout.addWidget(self.card_cartao, 0, 3)
        cards_layout.addWidget(self.card_suprimentos, 1, 0)
        cards_layout.addWidget(self.card_sangrias, 1, 1)
        cards_layout.addWidget(self.card_prazo, 1, 2)
        cards_layout.addWidget(self.card_recebimentos_fiado, 1, 3)
        cards_layout.addWidget(self.card_total_geral, 2, 0)

        layout.addLayout(cards_layout)

        # ---- ações ----

        acoes_layout = QHBoxLayout()
        acoes_layout.setSpacing(10)

        self.bt_suprimento = QPushButton("+ Suprimento")
        self.bt_suprimento.setMinimumHeight(46)
        self.bt_suprimento.setStyleSheet("""
            QPushButton {
                background:white;
                color:#2E7D32;
                border:1px solid #2E7D32;
                border-radius:10px;
                font-weight:bold;
                padding:0 18px;
            }
            QPushButton:hover {
                background:#e8f5e9;
            }
        """)
        self.bt_suprimento.clicked.connect(self.suprimento)

        self.bt_sangria = QPushButton("- Sangria")
        self.bt_sangria.setMinimumHeight(46)
        self.bt_sangria.setStyleSheet("""
            QPushButton {
                background:white;
                color:#C62828;
                border:1px solid #C62828;
                border-radius:10px;
                font-weight:bold;
                padding:0 18px;
            }
            QPushButton:hover {
                background:#ffebee;
            }
        """)
        self.bt_sangria.clicked.connect(self.sangria)

        self.bt_encerrar = QPushButton("Encerrar Caixa")
        self.bt_encerrar.setMinimumHeight(46)
        self.bt_encerrar.setStyleSheet("""
            QPushButton {
                background:#202225;
                color:white;
                border-radius:10px;
                padding:0 22px;
                font-weight:bold;
            }
            QPushButton:hover {
                background:#3a3d42;
            }
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
        lbl_historico_titulo.setStyleSheet(
            "font-size:11px; font-weight:bold; color:gray;"
        )

        self.bt_atualizar_historico = QPushButton("Atualizar")
        self.bt_atualizar_historico.setStyleSheet("""
            QPushButton {
                background:#616161;
                color:white;
                font-weight:bold;
                border-radius:8px;
                padding:6px 14px;
                font-size:11px;
            }
            QPushButton:hover {
                background:#424242;
            }
        """)
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
        self.tabela_movimentos.setStyleSheet("""
            QTableWidget {
                background:white;
                alternate-background-color:#f8f9fb;
                border:1px solid #e0e0e0;
                border-radius:10px;
                gridline-color:#eeeeee;
                color:#202225;
            }
            QTableWidget::item {
                color:#202225;
                background:transparent;
            }
            QHeaderView::section {
                background:#f4f5f7;
                color:#555;
                padding:6px;
                border:none;
                border-bottom:1px solid #e0e0e0;
                font-weight:bold;
            }
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

        self.card_troco.atualizar(
            f"R$ {float(resumo.get('saldo_inicial', 0) or 0):.2f}"
        )
        self.card_dinheiro.atualizar(
            f"R$ {float(resumo.get('vendas_dinheiro', 0) or 0):.2f}"
        )
        self.card_pix.atualizar(
            f"R$ {float(resumo.get('vendas_pix', 0) or 0):.2f}"
        )
        self.card_cartao.atualizar(
            f"R$ {float(resumo.get('vendas_cartao', 0) or 0):.2f}"
        )
        self.card_suprimentos.atualizar(
            f"+ R$ {float(resumo.get('suprimentos', 0) or 0):.2f}"
        )
        self.card_sangrias.atualizar(
            f"- R$ {float(resumo.get('sangrias', 0) or 0):.2f}"
        )
        self.card_prazo.atualizar(
            f"R$ {float(resumo.get('vendas_prazo', 0) or 0):.2f}"
        )
        self.card_recebimentos_fiado.atualizar(
            f"R$ {float(resumo.get('recebimentos_fiado', 0) or 0):.2f}"
        )
        self.card_total_geral.atualizar(
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
