from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
)

from design import tokens
from design.responsive import tamanho_fixo_seguro
from design.widgets import Card, BotaoPrimario, BotaoSecundario
from services import preferencias_service


# KPIs escondidos de fábrica (quem nunca personalizou o Início): contagens
# que quase não mudam no dia ou que já aparecem em outro bloco (estoque
# em alerta está no quadro de Alertas). Ficam disponíveis pra ligar aqui.
KPIS_OCULTOS_PADRAO = ("ticket", "clientes", "produtos", "estoque")


def _reordenar_ids(registro, ordem_salva):

    ids_registro = [c["id"] for c in registro]

    if not ordem_salva:
        return ids_registro

    ordenado = [i for i in ordem_salva if i in ids_registro]
    restantes = [i for i in ids_registro if i not in ordenado]

    return ordenado + restantes


class PersonalizarDashboardDialog(QDialog):
    """Mostrar/ocultar e reordenar os cards do dashboard. Primeiro corte
    deliberadamente simples (checkbox + setas ▲▼) em vez de
    drag-and-drop — não existe nenhum precedente de DnD no projeto hoje,
    então essa é a opção de menor risco pra entregar personalização real
    sem construir mecânica nova do Qt do zero."""

    def __init__(self, usuario_id, registro_kpis, registro_paineis, parent=None):

        super().__init__(parent)

        self.usuario_id = usuario_id
        self.registro_kpis = registro_kpis
        self.registro_paineis = registro_paineis

        self.setWindowTitle("Personalizar Dashboard")
        tamanho_fixo_seguro(self, 460, 560)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        ordem_salva, ocultos_kpis = self._preferencia_kpis()
        self.ordem_kpis = _reordenar_ids(registro_kpis, ordem_salva)
        self.ocultos_kpis = set(ocultos_kpis)
        self.ocultos_paineis = set(self._preferencia_paineis_ocultos())

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(24, 24, 24, 20)
        raiz.setSpacing(16)

        titulo = QLabel("Personalizar Dashboard")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)
        raiz.addWidget(titulo)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        corpo = QWidget()
        corpo.setStyleSheet("background:transparent;")

        layout_corpo = QVBoxLayout(corpo)
        layout_corpo.setContentsMargins(0, 0, 0, 0)
        layout_corpo.setSpacing(16)

        self.card_kpis = self._secao_kpis()
        layout_corpo.addWidget(self.card_kpis)
        layout_corpo.addWidget(self._secao_paineis())
        layout_corpo.addStretch()

        scroll.setWidget(corpo)
        raiz.addWidget(scroll, stretch=1)

        rodape = QHBoxLayout()
        rodape.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.clicked.connect(self.reject)

        bt_salvar = BotaoPrimario("Salvar")
        bt_salvar.clicked.connect(self.salvar)

        rodape.addWidget(bt_cancelar)
        rodape.addWidget(bt_salvar)

        raiz.addLayout(rodape)

    # ======================================
    # PREFERÊNCIAS ATUAIS
    # ======================================

    def _preferencia_kpis(self):
        salvo = preferencias_service.carregar(self.usuario_id, "dashboard_kpis", {})
        if not salvo:
            return [], list(KPIS_OCULTOS_PADRAO)
        return salvo.get("ordem", []), salvo.get("ocultos", [])

    def _preferencia_paineis_ocultos(self):
        salvo = preferencias_service.carregar(self.usuario_id, "dashboard_paineis", {})
        return salvo.get("ocultos", [])

    # ======================================
    # SEÇÃO KPIS (mostrar/ocultar + reordenar)
    # ======================================

    def _secao_kpis(self):

        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        rotulo = QLabel("KPIS — MOSTRAR E REORDENAR")
        rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700; letter-spacing:0.5px;
        """)
        layout.addWidget(rotulo)

        self.container_kpis = QVBoxLayout()
        self.container_kpis.setSpacing(4)
        layout.addLayout(self.container_kpis)

        self._redesenhar_kpis()

        return card

    def _redesenhar_kpis(self):

        while self.container_kpis.count():
            item = self.container_kpis.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        indice_por_id = {c["id"]: c for c in self.registro_kpis}
        total = len(self.ordem_kpis)

        for i, card_id in enumerate(self.ordem_kpis):
            card = indice_por_id[card_id]
            self.container_kpis.addWidget(
                self._linha_kpi(card_id, card["titulo"], i, total)
            )

    def _linha_kpi(self, card_id, titulo, indice, total):

        linha = QFrame()
        linha.setStyleSheet("background:transparent;")

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        check = QCheckBox(titulo)
        check.setChecked(card_id not in self.ocultos_kpis)
        check.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px;
        """)
        check.toggled.connect(lambda marcado, cid=card_id: self._alternar_kpi(cid, marcado))
        layout.addWidget(check, stretch=1)

        bt_subir = self._botao_seta("▲", indice > 0)
        bt_subir.clicked.connect(lambda _, cid=card_id: self._mover_kpi(cid, -1))

        bt_descer = self._botao_seta("▼", indice < total - 1)
        bt_descer.clicked.connect(lambda _, cid=card_id: self._mover_kpi(cid, 1))

        layout.addWidget(bt_subir)
        layout.addWidget(bt_descer)

        return linha

    def _botao_seta(self, texto, habilitado):

        botao = QPushButton(texto)
        botao.setFixedSize(28, 28)
        botao.setEnabled(habilitado)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setStyleSheet(f"""
            QPushButton {{
                border:1px solid {tokens.BORDA}; border-radius:6px;
                background:{tokens.CARD}; color:{tokens.TEXTO_SECUNDARIO};
                font-size:{tokens.TAMANHO_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA}; }}
            QPushButton:disabled {{ color:{tokens.TEXTO_TERCIARIO}; border-color:{tokens.BORDA}; }}
        """)

        return botao

    def _alternar_kpi(self, card_id, marcado):
        if marcado:
            self.ocultos_kpis.discard(card_id)
        else:
            self.ocultos_kpis.add(card_id)

    def _mover_kpi(self, card_id, delta):

        i = self.ordem_kpis.index(card_id)
        novo_i = i + delta

        if 0 <= novo_i < len(self.ordem_kpis):
            self.ordem_kpis[i], self.ordem_kpis[novo_i] = (
                self.ordem_kpis[novo_i], self.ordem_kpis[i],
            )
            self._redesenhar_kpis()

    # ======================================
    # SEÇÃO PAINÉIS (só mostrar/ocultar)
    # ======================================

    def _secao_paineis(self):

        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        rotulo = QLabel("PAINÉIS — MOSTRAR/OCULTAR")
        rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700; letter-spacing:0.5px;
        """)
        layout.addWidget(rotulo)

        for painel in self.registro_paineis:

            check = QCheckBox(painel["titulo"])
            check.setChecked(painel["id"] not in self.ocultos_paineis)
            check.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO};
                font-size:{tokens.TAMANHO_MD}px;
            """)
            check.toggled.connect(
                lambda marcado, pid=painel["id"]: self._alternar_painel(pid, marcado)
            )
            layout.addWidget(check)

        return card

    def _alternar_painel(self, painel_id, marcado):
        if marcado:
            self.ocultos_paineis.discard(painel_id)
        else:
            self.ocultos_paineis.add(painel_id)

    # ======================================
    # SALVAR
    # ======================================

    def salvar(self):

        preferencias_service.salvar(
            self.usuario_id,
            "dashboard_kpis",
            {"ordem": self.ordem_kpis, "ocultos": list(self.ocultos_kpis)},
        )
        preferencias_service.salvar(
            self.usuario_id,
            "dashboard_paineis",
            {"ocultos": list(self.ocultos_paineis)},
        )

        self.accept()
