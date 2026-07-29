from datetime import date, datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QMessageBox,
)

from services.api import configuracoes
from services.conta_pagar_service import (
    listar_contas_pagar,
    excluir_conta_pagar,
    pagar_conta_pagar,
)
from telas.cadastro_despesa import CadastroDespesaDialog


def _formatar_moeda(valor):
    return (
        f"R$ {float(valor):,.2f}".replace(",", "X")
        .replace(".", ",").replace("X", ".")
    )


def _status_real(conta):
    """PENDENTE com vencimento no passado vira VENCIDA na visualizacao
    — o backend nunca grava esse status, e essa e a unica derivacao
    que importa mostrar pro usuario (nao faz sentido gravar VENCIDA
    persistido, ja que o mesmo registro fica cada vez mais vencido
    conforme o tempo passa sem nenhuma acao)."""

    status = conta.get("status", "PENDENTE")

    if status != "PENDENTE":
        return status

    try:
        vencimento = datetime.fromisoformat(
            conta["data_vencimento"]
        ).date()
    except (ValueError, TypeError, KeyError):
        return status

    if vencimento < date.today():
        return "VENCIDA"

    return status


class CardResumo(QFrame):

    def __init__(self, titulo, subtitulo, cor):

        super().__init__()

        self.setStyleSheet("""
            QFrame {
                background:#202225;
                border-radius:12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(4)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            "background:transparent; border:none; font-size:11px; "
            "font-weight:bold; color:#9E9E9E; letter-spacing:1px;"
        )

        self.lbl_valor = QLabel("R$ 0,00")
        self.lbl_valor.setStyleSheet(
            f"background:transparent; border:none; font-size:24px; "
            f"font-weight:bold; color:{cor};"
        )

        self.lbl_subtitulo = QLabel(subtitulo)
        self.lbl_subtitulo.setStyleSheet(
            "background:transparent; border:none; font-size:11px; "
            "color:#757575;"
        )

        layout.addWidget(lbl_titulo)
        layout.addWidget(self.lbl_valor)
        layout.addWidget(self.lbl_subtitulo)

    def atualizar(self, valor_texto, subtitulo=None):
        self.lbl_valor.setText(valor_texto)
        if subtitulo is not None:
            self.lbl_subtitulo.setText(subtitulo)


class DespesaCard(QFrame):

    editar_solicitado = Signal(dict)
    excluir_solicitado = Signal(dict)
    pagar_solicitado = Signal(dict)

    CORES_STATUS = {
        "PAGO": ("#2E7D32", "#E8F5E9", "Paga"),
        "PENDENTE": ("#F9A825", "#FFF8E1", "Pendente"),
        "VENCIDA": ("#C62828", "#FFEBEE", "Vencida"),
        "CANCELADO": ("#9E9E9E", "#F5F5F5", "Cancelada"),
    }

    def __init__(self, conta):

        super().__init__()

        self.conta = conta

        self.setStyleSheet("""
            QFrame {
                background:white;
                border-radius:12px;
                border:1px solid #eeeeee;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        status = _status_real(conta)
        cor, cor_fundo, texto_status = self.CORES_STATUS.get(
            status, ("#616161", "#F5F5F5", status)
        )

        icone = QLabel("↘")
        icone.setFixedSize(40, 40)
        icone.setAlignment(Qt.AlignCenter)
        icone.setStyleSheet(f"""
            background:{cor_fundo};
            color:{cor};
            border-radius:20px;
            font-size:16px;
            font-weight:bold;
            border:none;
        """)

        layout.addWidget(icone)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(4)

        topo = QHBoxLayout()
        topo.setSpacing(8)

        badge_status = QLabel(texto_status)
        badge_status.setStyleSheet(f"""
            background:{cor_fundo};
            color:{cor};
            border-radius:8px;
            padding:2px 10px;
            font-size:11px;
            font-weight:bold;
            border:none;
        """)

        topo.addWidget(badge_status)

        categoria = conta.get("categoria")

        if categoria:
            badge_categoria = QLabel(categoria.upper())
            badge_categoria.setStyleSheet("""
                background:transparent;
                color:#9E9E9E;
                font-size:11px;
                font-weight:bold;
                border:none;
            """)
            topo.addWidget(badge_categoria)

        topo.addStretch()

        col_texto.addLayout(topo)

        descricao = QLabel(conta.get("descricao") or "Despesa")
        descricao.setStyleSheet(
            "background:transparent; border:none; font-size:14px; "
            "font-weight:bold; color:#202225;"
        )
        col_texto.addWidget(descricao)

        vencimento_texto = conta.get("data_vencimento", "")
        try:
            vencimento_formatado = datetime.fromisoformat(
                vencimento_texto
            ).strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            vencimento_formatado = vencimento_texto

        lbl_vencimento = QLabel(f"📅 Vencimento: {vencimento_formatado}")
        lbl_vencimento.setStyleSheet(
            "background:transparent; border:none; font-size:12px; "
            "color:#9E9E9E;"
        )
        col_texto.addWidget(lbl_vencimento)

        layout.addLayout(col_texto, stretch=1)

        lbl_valor = QLabel(_formatar_moeda(conta.get("valor", 0)))
        lbl_valor.setStyleSheet(
            "background:transparent; border:none; font-size:18px; "
            "font-weight:bold; color:#202225;"
        )
        layout.addWidget(lbl_valor)

        acoes = QHBoxLayout()
        acoes.setSpacing(4)

        if status in ("PENDENTE", "VENCIDA"):

            bt_pagar = QPushButton("Pagar")
            bt_pagar.setCursor(Qt.PointingHandCursor)
            bt_pagar.setStyleSheet("""
                QPushButton {
                    background:#2E7D32;
                    color:white;
                    border-radius:8px;
                    padding:6px 14px;
                    font-size:12px;
                    font-weight:bold;
                    border:none;
                }
                QPushButton:hover {
                    background:#1B5E20;
                }
            """)
            bt_pagar.clicked.connect(
                lambda: self.pagar_solicitado.emit(self.conta)
            )
            acoes.addWidget(bt_pagar)

        bt_editar = QPushButton("✏")
        bt_editar.setFixedSize(34, 34)
        bt_editar.setCursor(Qt.PointingHandCursor)
        bt_editar.setStyleSheet("""
            QPushButton {
                background:#E3F2FD;
                color:#1565C0;
                border-radius:8px;
                border:none;
            }
            QPushButton:hover {
                background:#BBDEFB;
            }
        """)
        bt_editar.clicked.connect(
            lambda: self.editar_solicitado.emit(self.conta)
        )

        bt_excluir = QPushButton("🗑")
        bt_excluir.setFixedSize(34, 34)
        bt_excluir.setCursor(Qt.PointingHandCursor)
        bt_excluir.setStyleSheet("""
            QPushButton {
                background:#FFEBEE;
                color:#C62828;
                border-radius:8px;
                border:none;
            }
            QPushButton:hover {
                background:#FFCDD2;
            }
        """)
        bt_excluir.clicked.connect(
            lambda: self.excluir_solicitado.emit(self.conta)
        )

        acoes.addWidget(bt_editar)
        acoes.addWidget(bt_excluir)

        layout.addLayout(acoes)


class ContasPagar(QWidget):

    voltar = Signal()

    FILTROS = ["TODAS", "PAGA", "PENDENTE", "VENCIDA"]

    def __init__(self):
        super().__init__()

        self.contas = []
        self.filtro_atual = "TODAS"

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:#f4f5f7;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()

        self.bt_voltar = QPushButton("← Voltar")
        self.bt_voltar.setStyleSheet("""
            QPushButton {
                background:transparent;
                color:gray;
                border:none;
                font-size:13px;
            }
            QPushButton:hover {
                color:#202225;
            }
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        config = configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"

        titulo = QLabel(nome_loja)
        titulo.setStyleSheet(
            "background:transparent; font-size:20px; "
            "font-weight:bold; color:#202225;"
        )

        subtitulo = QLabel("LOJA OPERACIONAL")
        subtitulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "color:#2E7D32; font-weight:bold;"
        )

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addSpacing(12)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()

        self.bt_nova_despesa = QPushButton("＋ Nova Despesa")
        self.bt_nova_despesa.setCursor(Qt.PointingHandCursor)
        self.bt_nova_despesa.setStyleSheet("""
            QPushButton {
                background:#C62828;
                color:white;
                border-radius:8px;
                padding:10px 18px;
                font-weight:bold;
            }
            QPushButton:hover {
                background:#8E1616;
            }
        """)
        self.bt_nova_despesa.clicked.connect(self.nova_despesa)

        cabecalho.addWidget(self.bt_nova_despesa)

        layout.addLayout(cabecalho)

        # ======================
        # CARDS DE RESUMO
        # ======================

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self.card_previsao = CardResumo(
            "PREVISÃO TOTAL", "total acumulado", "#EF5350"
        )
        self.card_pago = CardResumo(
            "TOTAL PAGO", "liquidadas", "#66BB6A"
        )
        self.card_aberto = CardResumo(
            "EM ABERTO", "a vencer", "#FFA726"
        )
        self.card_vencidas = CardResumo(
            "VENCIDAS", "tudo em dia", "#EF5350"
        )

        cards_layout.addWidget(self.card_previsao)
        cards_layout.addWidget(self.card_pago)
        cards_layout.addWidget(self.card_aberto)
        cards_layout.addWidget(self.card_vencidas)

        layout.addLayout(cards_layout)

        # ======================
        # FILTROS
        # ======================

        filtro_layout = QHBoxLayout()
        filtro_layout.setSpacing(8)

        self.botoes_filtro = {}

        for filtro in self.FILTROS:

            botao = QPushButton(filtro.capitalize())
            botao.setCheckable(True)
            botao.setCursor(Qt.PointingHandCursor)
            botao.setMinimumHeight(34)
            botao.setStyleSheet("""
                QPushButton {
                    background:white;
                    color:#616161;
                    border:1px solid #dcdcdc;
                    border-radius:17px;
                    padding:0 18px;
                    font-size:12px;
                    font-weight:bold;
                }
                QPushButton:checked {
                    background:#C62828;
                    color:white;
                    border:1px solid #C62828;
                }
            """)
            botao.clicked.connect(
                lambda _checked, f=filtro: self._filtrar(f)
            )

            self.botoes_filtro[filtro] = botao
            filtro_layout.addWidget(botao)

        filtro_layout.addStretch()

        layout.addLayout(filtro_layout)

        self.botoes_filtro["TODAS"].setChecked(True)

        # ======================
        # LISTA
        # ======================

        self.area_rolagem = QScrollArea()
        self.area_rolagem.setWidgetResizable(True)
        self.area_rolagem.setStyleSheet(
            "QScrollArea { border:none; background:transparent; }"
        )

        self.lista_widget = QWidget()
        self.lista_widget.setStyleSheet("background:transparent;")

        self.lista_layout = QVBoxLayout(self.lista_widget)
        self.lista_layout.setSpacing(10)
        self.lista_layout.setAlignment(Qt.AlignTop)

        self.area_rolagem.setWidget(self.lista_widget)

        layout.addWidget(self.area_rolagem, stretch=1)

    # ==========================================
    # CARREGAMENTO
    # ==========================================

    def carregar(self):

        self.contas = listar_contas_pagar()

        self._atualizar_cards()
        self._renderizar_lista()

    def _atualizar_cards(self):

        contas_validas = [
            c for c in self.contas
            if c.get("status") != "CANCELADO"
        ]

        previsao_total = sum(
            float(c.get("valor", 0)) for c in contas_validas
        )

        total_pago = sum(
            float(c.get("valor", 0)) for c in contas_validas
            if c.get("status") == "PAGO"
        )

        em_aberto = sum(
            float(c.get("valor", 0)) for c in contas_validas
            if _status_real(c) == "PENDENTE"
        )

        vencidas_lista = [
            c for c in contas_validas
            if _status_real(c) == "VENCIDA"
        ]

        vencidas_total = sum(
            float(c.get("valor", 0)) for c in vencidas_lista
        )

        self.card_previsao.atualizar(_formatar_moeda(previsao_total))
        self.card_pago.atualizar(_formatar_moeda(total_pago))
        self.card_aberto.atualizar(_formatar_moeda(em_aberto))

        if vencidas_lista:
            self.card_vencidas.atualizar(
                _formatar_moeda(vencidas_total),
                f"{len(vencidas_lista)} conta(s) vencida(s)",
            )
        else:
            self.card_vencidas.atualizar(
                _formatar_moeda(0), "Tudo em dia"
            )

    def _filtrar(self, filtro):

        self.filtro_atual = filtro

        for nome, botao in self.botoes_filtro.items():
            botao.setChecked(nome == filtro)

        self._renderizar_lista()

    def _renderizar_lista(self):

        while self.lista_layout.count():
            item = self.lista_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        filtro = self.filtro_atual

        if filtro == "TODAS":
            contas_filtradas = [
                c for c in self.contas
                if c.get("status") != "CANCELADO"
            ]
        else:
            contas_filtradas = [
                c for c in self.contas
                if _status_real(c) == filtro
            ]

        if not contas_filtradas:

            lbl_vazio = QLabel(
                "Nenhuma despesa encontrada nesse filtro."
            )
            lbl_vazio.setAlignment(Qt.AlignCenter)
            lbl_vazio.setStyleSheet(
                "color:#9E9E9E; font-size:13px; padding:40px; "
                "background:transparent;"
            )
            self.lista_layout.addWidget(lbl_vazio)
            return

        contas_ordenadas = sorted(
            contas_filtradas,
            key=lambda c: c.get("data_vencimento", ""),
        )

        for conta in contas_ordenadas:

            card = DespesaCard(conta)
            card.editar_solicitado.connect(self.editar_despesa)
            card.excluir_solicitado.connect(self.excluir_despesa)
            card.pagar_solicitado.connect(self.pagar_despesa)

            self.lista_layout.addWidget(card)

    # ==========================================
    # AÇÕES
    # ==========================================

    def nova_despesa(self):

        dialogo = CadastroDespesaDialog(parent=self)

        if dialogo.exec() == dialogo.DialogCode.Accepted:
            self.carregar()

    def editar_despesa(self, conta):

        dialogo = CadastroDespesaDialog(conta=conta, parent=self)

        if dialogo.exec() == dialogo.DialogCode.Accepted:
            self.carregar()

    def excluir_despesa(self, conta):

        resposta = QMessageBox.question(
            self,
            "Excluir despesa",
            f"Excluir a despesa \"{conta.get('descricao')}\"?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_conta_pagar(conta["id"])

        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def pagar_despesa(self, conta):

        response = pagar_conta_pagar(conta["id"])

        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
