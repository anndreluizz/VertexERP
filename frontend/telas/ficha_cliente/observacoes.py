from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QMessageBox,
)

from services.cliente_service import (
    listar_observacoes_cliente,
    criar_observacao_cliente,
    excluir_observacao_cliente,
)
from services.worker import rodar_em_thread
from design import tokens
from design.widgets import (
    BotaoPrimario,
    CampoTexto,
    Card,
)
from telas.ficha_cliente.comum import _parse_data


class ObservacoesMixin:
    """Aba de observacoes da ficha."""

    def _construir_pagina_observacoes(self):
        """Antes era a 4ª aba ('Observações'); agora mora dentro do
        painel lateral recolhível, embaixo do Resumo -- por isso ganha
        uma altura limitada (rolagem própria) em vez de ocupar a tela
        inteira como fazia quando era uma aba dedicada."""

        pagina = QFrame()
        pagina.setStyleSheet("background:transparent;")

        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        linha_nova = QVBoxLayout()
        linha_nova.setSpacing(6)

        self.campo_nova_observacao = CampoTexto(
            "Escreva uma observação..."
        )

        self.bt_add_observacao = BotaoPrimario("Adicionar")
        self.bt_add_observacao.setFixedHeight(36)
        self.bt_add_observacao.setAutoDefault(False)
        self.bt_add_observacao.clicked.connect(self.adicionar_observacao)

        linha_nova.addWidget(self.campo_nova_observacao)
        linha_nova.addWidget(self.bt_add_observacao)

        layout.addLayout(linha_nova)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # sem altura minima -- essa lista tem rolagem própria, não pode
        # ser o que impede o painel (e o diálogo inteiro) de encolher
        # numa tela menor (ver _dimensionar_e_centralizar)
        scroll.setMinimumHeight(0)
        scroll.setMaximumHeight(260)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        conteudo = QFrame()
        conteudo.setStyleSheet("background:transparent;")

        self.layout_observacoes = QVBoxLayout(conteudo)
        self.layout_observacoes.setContentsMargins(0, 0, 6, 0)
        self.layout_observacoes.setSpacing(8)
        self.layout_observacoes.addStretch()

        scroll.setWidget(conteudo)
        layout.addWidget(scroll)

        return pagina

    def _preencher_observacoes(self, observacoes):

        while self.layout_observacoes.count():
            item = self.layout_observacoes.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not observacoes:
            vazio = QLabel("Nenhuma observação registrada ainda.")
            vazio.setAlignment(Qt.AlignCenter)
            vazio.setWordWrap(True)
            vazio.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_SM}px; padding:8px;
            """)
            self.layout_observacoes.addWidget(vazio)
            self.layout_observacoes.addStretch()
            return

        for obs in observacoes:
            self.layout_observacoes.addWidget(self._linha_observacao(obs))

        self.layout_observacoes.addStretch()

    def _linha_observacao(self, obs):

        linha = Card()

        layout = QVBoxLayout(linha)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        cabecalho = QHBoxLayout()

        data = _parse_data(obs.get("criado_em"))
        texto_data = data.strftime("%d/%m/%Y %H:%M") if data else "—"

        lbl_data = QLabel(texto_data)
        lbl_data.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        bt_excluir = QPushButton("Excluir")
        bt_excluir.setCursor(Qt.PointingHandCursor)
        bt_excluir.setAutoDefault(False)
        bt_excluir.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; color:{tokens.ERRO};
                font-size:{tokens.TAMANHO_XS}px; font-weight:700;
            }}
            QPushButton:hover {{ text-decoration: underline; }}
        """)
        bt_excluir.clicked.connect(
            lambda _, oid=obs["id"]: self.excluir_observacao(oid)
        )

        cabecalho.addWidget(lbl_data)
        cabecalho.addStretch()
        cabecalho.addWidget(bt_excluir)

        lbl_texto = QLabel(obs.get("texto", ""))
        lbl_texto.setWordWrap(True)
        lbl_texto.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px;
        """)

        layout.addLayout(cabecalho)
        layout.addWidget(lbl_texto)

        return linha

    def _carregar_observacoes(self):
        rodar_em_thread(
            self,
            listar_observacoes_cliente,
            self.cliente["id"],
            ao_sucesso=self._preencher_observacoes,
        )

    def adicionar_observacao(self):

        texto = self.campo_nova_observacao.text().strip()

        if not texto:
            return

        self.bt_add_observacao.setEnabled(False)

        rodar_em_thread(
            self,
            criar_observacao_cliente,
            self.cliente["id"],
            texto,
            ao_sucesso=self._ao_adicionar_observacao_sucesso,
            ao_erro=self._ao_observacao_erro,
            ao_finalizar=self._ao_adicionar_observacao_finalizado,
        )

    def _ao_adicionar_observacao_sucesso(self, response):
        if response.status_code in (200, 201):
            self.campo_nova_observacao.clear()
            self._carregar_observacoes()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_adicionar_observacao_finalizado(self):
        self.bt_add_observacao.setEnabled(True)

    def _ao_observacao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def excluir_observacao(self, observacao_id):

        resposta = QMessageBox.question(
            self, "Excluir Observação", "Deseja excluir esta observação?"
        )

        if resposta != QMessageBox.Yes:
            return

        rodar_em_thread(
            self,
            excluir_observacao_cliente,
            self.cliente["id"],
            observacao_id,
            ao_sucesso=self._ao_excluir_observacao_sucesso,
            ao_erro=self._ao_observacao_erro,
        )

    def _ao_excluir_observacao_sucesso(self, response):
        if response.status_code == 200:
            self._carregar_observacoes()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))
