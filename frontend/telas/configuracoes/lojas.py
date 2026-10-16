from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QFrame,
    QMessageBox,
    QComboBox,
)

from services import preferencias_service
from services import loja_service
from services.worker import rodar_em_thread

from design import tokens
from design.widgets import (
    BotaoPrimario, BotaoSecundario, BotaoSucesso, CampoTexto,
)


class LojasMixin:
    """Pagina Lojas: listar, criar, renomear, ativar e loja deste terminal."""

    def _criar_pagina_lojas(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # ---- loja deste terminal ----

        lbl_terminal = QLabel("Loja deste terminal")
        lbl_terminal.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:800; color:{tokens.TEXTO_SECUNDARIO}; letter-spacing:0.6px;
        """)
        layout.addWidget(lbl_terminal)

        dica_terminal = QLabel(
            "Toda venda, movimento de caixa e ajuste de estoque feito "
            "neste computador é registrado nessa loja — não importa "
            "qual usuário estiver logado. Configure uma vez por "
            "instalação."
        )
        dica_terminal.setWordWrap(True)
        dica_terminal.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO}; line-height:1.5;
        """)
        layout.addWidget(dica_terminal)

        linha_terminal = QHBoxLayout()
        linha_terminal.setSpacing(10)

        self.combo_loja_terminal = QComboBox()
        self.combo_loja_terminal.setMinimumHeight(44)
        self.combo_loja_terminal.setCursor(Qt.PointingHandCursor)
        self.combo_loja_terminal.setStyleSheet(f"""
            QComboBox {{
                border:1.5px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:0 12px; font-size:{tokens.TAMANHO_MD}px; color:{tokens.TEXTO};
            }}
        """)

        bt_salvar_loja_terminal = BotaoPrimario("Salvar")
        bt_salvar_loja_terminal.setMinimumHeight(44)
        bt_salvar_loja_terminal.clicked.connect(self._salvar_loja_do_terminal)

        linha_terminal.addWidget(self.combo_loja_terminal, stretch=1)
        linha_terminal.addWidget(bt_salvar_loja_terminal)

        layout.addLayout(linha_terminal)

        linha_divisoria = QFrame()
        linha_divisoria.setFixedHeight(1)
        linha_divisoria.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(linha_divisoria)

        # ---- lojas cadastradas ----

        lbl_cadastradas = QLabel("Lojas cadastradas")
        lbl_cadastradas.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(lbl_cadastradas)

        self.lista_lojas = QVBoxLayout()
        self.lista_lojas.setSpacing(6)
        layout.addLayout(self.lista_lojas)

        linha_nova_loja = QHBoxLayout()
        linha_nova_loja.setSpacing(10)

        self.campo_nova_loja = CampoTexto("Ex: Filial Centro")
        self.campo_nova_loja.returnPressed.connect(self._criar_loja)

        bt_criar_loja = BotaoSucesso("+ Adicionar")
        bt_criar_loja.clicked.connect(self._criar_loja)

        linha_nova_loja.addWidget(self.campo_nova_loja, stretch=1)
        linha_nova_loja.addWidget(bt_criar_loja)

        layout.addLayout(linha_nova_loja)

        layout.addStretch()

        self._carregar_lojas()

        return self._envolver_com_rolagem(pagina, 7)

    def _carregar_lojas(self):

        rodar_em_thread(
            self,
            loja_service.listar_lojas,
            True,
            ao_sucesso=self._ao_carregar_lojas_sucesso,
            ao_erro=self._ao_carregar_lojas_erro,
        )

    def _ao_carregar_lojas_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar as lojas.\n{erro}")

    def _ao_carregar_lojas_sucesso(self, lojas):

        while self.lista_lojas.count():
            item = self.lista_lojas.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.combo_loja_terminal.blockSignals(True)
        self.combo_loja_terminal.clear()
        self.combo_loja_terminal.addItem("(usar a loja do usuário)", None)

        loja_atual = preferencias_service.carregar_loja_id()

        for loja in lojas:

            # desativada so' aparece se ja for a deste terminal
            if loja["ativa"] or loja_atual == loja["id"]:
                self.combo_loja_terminal.addItem(
                    loja["nome"] + ("" if loja["ativa"] else " (desativada)"),
                    loja["id"],
                )

                if loja_atual == loja["id"]:
                    self.combo_loja_terminal.setCurrentIndex(
                        self.combo_loja_terminal.count() - 1
                    )

            self.lista_lojas.addWidget(self._linha_loja(loja))

        self.combo_loja_terminal.blockSignals(False)

        if not lojas:
            lbl_vazio = QLabel("Nenhuma loja cadastrada ainda.")
            lbl_vazio.setStyleSheet(f"""
                background:transparent; font-size:{tokens.TAMANHO_SM}px;
                color:{tokens.TEXTO_TERCIARIO};
            """)
            self.lista_lojas.addWidget(lbl_vazio)

    def _linha_loja(self, loja):

        linha = QWidget()
        linha.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl_loja = QLabel(
            f"•  {loja['nome']}" + ("" if loja["ativa"] else "  (desativada)")
        )
        lbl_loja.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO if loja["ativa"] else tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(lbl_loja, stretch=1)

        bt_renomear = BotaoSecundario("Renomear")
        bt_renomear.clicked.connect(lambda: self._renomear_loja(loja))
        layout.addWidget(bt_renomear)

        bt_ativa = BotaoSecundario("Desativar" if loja["ativa"] else "Ativar")
        bt_ativa.clicked.connect(lambda: self._alternar_loja_ativa(loja))
        layout.addWidget(bt_ativa)

        return linha

    def _renomear_loja(self, loja):

        nome, ok = QInputDialog.getText(
            self, "Renomear loja", "Novo nome:", text=loja["nome"]
        )

        if ok and nome.strip() and nome.strip() != loja["nome"]:
            self._atualizar_loja(loja["id"], nome=nome.strip())

    def _alternar_loja_ativa(self, loja):

        if loja["ativa"]:
            resposta = QMessageBox.question(
                self,
                "Desativar loja",
                f"Desativar \"{loja['nome']}\"? Ela some das listas de "
                "escolha, mas as vendas e contas dela continuam guardadas.",
            )
            if resposta != QMessageBox.Yes:
                return

        self._atualizar_loja(loja["id"], ativa=not loja["ativa"])

    def _atualizar_loja(self, loja_id, **campos):

        rodar_em_thread(
            self,
            loja_service.atualizar_loja,
            loja_id,
            **campos,
            ao_sucesso=self._ao_criar_loja_sucesso,
            ao_erro=self._ao_criar_loja_erro,
        )

    def _salvar_loja_do_terminal(self):

        loja_id = self.combo_loja_terminal.currentData()

        preferencias_service.salvar_loja_id(loja_id)

        QMessageBox.information(
            self,
            "Salvo",
            "Este terminal já está configurado. Vendas, caixa e "
            "estoque feitos aqui vão contar pra "
            f"\"{self.combo_loja_terminal.currentText()}\".",
        )

    def _criar_loja(self):

        nome = self.campo_nova_loja.text().strip()

        if not nome:
            return

        rodar_em_thread(
            self,
            loja_service.criar_loja,
            nome,
            ao_sucesso=self._ao_criar_loja_sucesso,
            ao_erro=self._ao_criar_loja_erro,
        )

    def _ao_criar_loja_sucesso(self, response):

        if response.status_code != 200:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        self.campo_nova_loja.clear()
        self._carregar_lojas()

    def _ao_criar_loja_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))
