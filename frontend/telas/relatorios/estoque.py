from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
)

from services.relatorio_service import (
    curva_abc,
    comparativo_estoque,
    sugestao_reposicao,
)
from services.worker import rodar_em_thread
from design import tokens
from utils.formatacao import formatar_moeda
from telas.relatorios.widgets import PainelSecao


class EstoqueMixin:
    """Aba Estoque: filtros, curva ABC, comparativo e sugestao de reposicao."""

    # ==========================================
    # PÁGINA: RELATÓRIO DE ESTOQUE
    # ==========================================

    def _criar_pagina_estoque(self):

        pagina, layout = self._pagina_rolavel(espacamento=12)

        filtro_layout = QHBoxLayout()
        filtro_layout.setSpacing(8)

        self.bt_estoque_todos = self._botao_filtro_estoque("Todos os Itens")
        self.bt_estoque_critico = self._botao_filtro_estoque(
            "Estoque Crítico"
        )
        self.bt_estoque_esgotado = self._botao_filtro_estoque("Esgotados")

        self.filtro_estoque_atual = "TODOS"

        self.bt_estoque_todos.clicked.connect(
            lambda: self._filtrar_estoque("TODOS")
        )
        self.bt_estoque_critico.clicked.connect(
            lambda: self._filtrar_estoque("CRITICO")
        )
        self.bt_estoque_esgotado.clicked.connect(
            lambda: self._filtrar_estoque("ESGOTADO")
        )

        filtro_layout.addWidget(self.bt_estoque_todos)
        filtro_layout.addWidget(self.bt_estoque_critico)
        filtro_layout.addWidget(self.bt_estoque_esgotado)
        filtro_layout.addStretch()

        layout.addLayout(filtro_layout)

        self.tabela_estoque = QTableWidget()
        self.tabela_estoque.setColumnCount(5)
        self.tabela_estoque.setHorizontalHeaderLabels([
            "Produto",
            "Categoria",
            "Preço Unit.",
            "Em Estoque",
            "Status",
        ])
        self._estilizar_tabela(self.tabela_estoque)

        self.tabela_estoque.setMinimumHeight(360)
        layout.addWidget(self.tabela_estoque)

        # ==========================================
        # CURVA ABC
        # ==========================================
        painel_abc = PainelSecao("📈", "Curva ABC de Produtos")

        filtro_abc = QHBoxLayout()
        filtro_abc.setSpacing(8)

        self.combo_periodo_abc = QComboBox()
        self.combo_periodo_abc.addItems(self.PERIODOS)
        self.combo_periodo_abc.setCurrentText("Este mês")
        self.combo_periodo_abc.setMinimumHeight(36)
        self.combo_periodo_abc.setCursor(Qt.PointingHandCursor)
        self.combo_periodo_abc.setStyleSheet(f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:4px 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """)

        self.combo_loja_abc = QComboBox()
        self.combo_loja_abc.setMinimumHeight(36)
        self.combo_loja_abc.setCursor(Qt.PointingHandCursor)
        self.combo_loja_abc.setStyleSheet(self.combo_periodo_abc.styleSheet())
        self._carregar_combo_lojas(self.combo_loja_abc)

        self._timer_atualizar_abc = QTimer(self)
        self._timer_atualizar_abc.setSingleShot(True)
        self._timer_atualizar_abc.timeout.connect(self._atualizar_curva_abc)
        self.combo_periodo_abc.currentTextChanged.connect(
            lambda: self._timer_atualizar_abc.start(300)
        )
        self.combo_loja_abc.currentIndexChanged.connect(
            lambda: self._timer_atualizar_abc.start(300)
        )

        filtro_abc.addWidget(self.combo_periodo_abc)
        filtro_abc.addWidget(self.combo_loja_abc)
        filtro_abc.addStretch()

        painel_abc.corpo.addLayout(filtro_abc)

        self.tabela_abc = QTableWidget()
        self.tabela_abc.setColumnCount(5)
        self.tabela_abc.setHorizontalHeaderLabels(
            ["Produto", "Quantidade", "Total", "% Acumulado", "Classe"]
        )
        self._estilizar_tabela(self.tabela_abc)
        self.tabela_abc.setMinimumHeight(260)
        painel_abc.corpo.addWidget(self.tabela_abc)

        layout.addWidget(painel_abc)

        # ==========================================
        # COMPARATIVO DE ESTOQUE ENTRE LOJAS
        # ==========================================
        painel_comparativo_estoque = PainelSecao(
            "🏬", "Comparativo de Estoque entre Lojas"
        )

        self.tabela_comparativo_estoque = QTableWidget()
        self.tabela_comparativo_estoque.setColumnCount(4)
        self.tabela_comparativo_estoque.setHorizontalHeaderLabels(
            ["Loja", "Quantidade Total", "Valor em Estoque", "Abaixo do Mínimo"]
        )
        self._estilizar_tabela(self.tabela_comparativo_estoque)
        self.tabela_comparativo_estoque.setMinimumHeight(150)
        painel_comparativo_estoque.corpo.addWidget(self.tabela_comparativo_estoque)

        layout.addWidget(painel_comparativo_estoque)

        # ==========================================
        # SUGESTÃO DE REPOSIÇÃO
        # ==========================================
        painel_reposicao = PainelSecao("🔄", "Sugestão de Reposição")

        subtitulo_reposicao = QLabel(
            "Esboço v1: lista quem está no mínimo ou abaixo e sugere "
            "completar até o mínimo -- não considera prazo de entrega "
            "do fornecedor nem sazonalidade, e não gera pedido nenhum "
            "sozinho."
        )
        subtitulo_reposicao.setWordWrap(True)
        subtitulo_reposicao.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; border:none;"
        )
        painel_reposicao.corpo.addWidget(subtitulo_reposicao)

        filtro_reposicao = QHBoxLayout()
        filtro_reposicao.setSpacing(8)

        self.combo_loja_reposicao = QComboBox()
        self.combo_loja_reposicao.setMinimumHeight(36)
        self.combo_loja_reposicao.setCursor(Qt.PointingHandCursor)
        self.combo_loja_reposicao.setStyleSheet(self.combo_periodo_abc.styleSheet())
        self._carregar_combo_lojas(self.combo_loja_reposicao)
        self.combo_loja_reposicao.currentIndexChanged.connect(
            self._atualizar_sugestao_reposicao
        )

        filtro_reposicao.addWidget(self.combo_loja_reposicao)
        filtro_reposicao.addStretch()

        painel_reposicao.corpo.addLayout(filtro_reposicao)

        self.tabela_reposicao = QTableWidget()
        self.tabela_reposicao.setColumnCount(4)
        self.tabela_reposicao.setHorizontalHeaderLabels(
            ["Produto", "Atual", "Mínimo", "Sugestão"]
        )
        self._estilizar_tabela(self.tabela_reposicao)
        self.tabela_reposicao.setMinimumHeight(220)
        painel_reposicao.corpo.addWidget(self.tabela_reposicao)

        layout.addWidget(painel_reposicao)

        layout.addStretch()

        return pagina

    def _botao_filtro_estoque(self, texto):

        botao = QPushButton(texto)
        botao.setCheckable(True)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setMinimumHeight(34)
        botao.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; color:{tokens.TEXTO_SECUNDARIO};
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_PILL}px;
                padding:0 16px; font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            }}
            QPushButton:checked {{
                background:{tokens.SIDEBAR}; color:white; border:1px solid {tokens.SIDEBAR};
            }}
        """)
        return botao

    def _status_estoque(self, produto):

        estoque = produto.get("estoque", 0)
        minimo = produto.get("estoque_minimo", 0)

        if estoque <= 0:
            return "ESGOTADO"

        if estoque <= minimo:
            return "CRITICO"

        return "NORMAL"

    def _filtrar_estoque(self, filtro):

        self.filtro_estoque_atual = filtro

        self.bt_estoque_todos.setChecked(filtro == "TODOS")
        self.bt_estoque_critico.setChecked(filtro == "CRITICO")
        self.bt_estoque_esgotado.setChecked(filtro == "ESGOTADO")

        self._atualizar_estoque()

    def _atualizar_estoque(self):

        criticos = sum(
            1 for p in self.produtos
            if self._status_estoque(p) == "CRITICO"
        )
        esgotados = sum(
            1 for p in self.produtos
            if self._status_estoque(p) == "ESGOTADO"
        )

        self.bt_estoque_critico.setText(f"Estoque Crítico ({criticos})")
        self.bt_estoque_esgotado.setText(f"Esgotados ({esgotados})")

        filtro = self.filtro_estoque_atual

        if filtro == "TODOS":
            produtos_filtrados = self.produtos
        else:
            produtos_filtrados = [
                p for p in self.produtos
                if self._status_estoque(p) == filtro
            ]

        self.tabela_estoque.setRowCount(0)

        cores_status = {
            "NORMAL": tokens.SECUNDARIA_HOVER,
            "CRITICO": tokens.ALERTA_TEXTO,
            "ESGOTADO": tokens.ERRO,
        }

        textos_status = {
            "NORMAL": "Normal",
            "CRITICO": "Crítico",
            "ESGOTADO": "Esgotado",
        }

        for produto in produtos_filtrados:

            linha = self.tabela_estoque.rowCount()
            self.tabela_estoque.insertRow(linha)

            status = self._status_estoque(produto)

            self.tabela_estoque.setItem(
                linha, 0, QTableWidgetItem(produto.get("nome", ""))
            )
            self.tabela_estoque.setItem(
                linha, 1,
                QTableWidgetItem(produto.get("categoria") or "—"),
            )
            self.tabela_estoque.setItem(
                linha, 2,
                QTableWidgetItem(
                    formatar_moeda(produto.get("preco_venda", 0))
                ),
            )
            self.tabela_estoque.setItem(
                linha, 3,
                QTableWidgetItem(str(produto.get("estoque", 0))),
            )

            item_status = QTableWidgetItem(textos_status[status])
            item_status.setForeground(QColor(cores_status[status]))
            self.tabela_estoque.setItem(linha, 4, item_status)

        self.tabela_estoque.setCurrentCell(-1, -1)
        self.tabela_estoque.clearSelection()

    # ==========================================
    # CURVA ABC
    # ==========================================

    def _atualizar_curva_abc(self):
        data_inicio, data_fim = self._calcular_periodo(self.combo_periodo_abc)
        loja_id = self.combo_loja_abc.currentData()

        rodar_em_thread(
            self,
            curva_abc,
            data_inicio,
            data_fim,
            loja_id,
            ao_sucesso=self._ao_atualizar_curva_abc_sucesso,
            ao_erro=self._ao_atualizar_secao_secundaria_erro,
        )

    def _ao_atualizar_curva_abc_sucesso(self, itens):

        cores_classe = {
            "A": tokens.SECUNDARIA_HOVER,
            "B": tokens.ALERTA_TEXTO,
            "C": tokens.ERRO,
        }

        self.tabela_abc.setRowCount(len(itens))

        for linha, item in enumerate(itens):
            self.tabela_abc.setItem(
                linha, 0, QTableWidgetItem(item["produto"])
            )
            self.tabela_abc.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade"]))
            )
            self.tabela_abc.setItem(
                linha, 2, QTableWidgetItem(formatar_moeda(item["total"]))
            )
            self.tabela_abc.setItem(
                linha, 3,
                QTableWidgetItem(f"{item['percentual_acumulado']:.1f}%".replace(".", ",")),
            )

            item_classe = QTableWidgetItem(item["classe"])
            item_classe.setForeground(
                QColor(cores_classe.get(item["classe"], tokens.TEXTO))
            )
            self.tabela_abc.setItem(linha, 4, item_classe)

    # ==========================================
    # COMPARATIVO DE ESTOQUE ENTRE LOJAS
    # ==========================================

    def _atualizar_comparativo_estoque(self):
        rodar_em_thread(
            self,
            comparativo_estoque,
            ao_sucesso=self._ao_atualizar_comparativo_estoque_sucesso,
            ao_erro=self._ao_atualizar_secao_secundaria_erro,
        )

    def _ao_atualizar_comparativo_estoque_sucesso(self, itens):

        self.tabela_comparativo_estoque.setRowCount(len(itens))

        for linha, item in enumerate(itens):
            self.tabela_comparativo_estoque.setItem(
                linha, 0, QTableWidgetItem(item["loja_nome"])
            )
            self.tabela_comparativo_estoque.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade_total"]))
            )
            self.tabela_comparativo_estoque.setItem(
                linha, 2,
                QTableWidgetItem(formatar_moeda(item["valor_em_estoque"])),
            )
            self.tabela_comparativo_estoque.setItem(
                linha, 3, QTableWidgetItem(str(item["produtos_abaixo_minimo"]))
            )

    # ==========================================
    # SUGESTÃO DE REPOSIÇÃO
    # ==========================================

    def _atualizar_sugestao_reposicao(self):
        loja_id = self.combo_loja_reposicao.currentData()

        rodar_em_thread(
            self,
            sugestao_reposicao,
            loja_id,
            ao_sucesso=self._ao_atualizar_sugestao_reposicao_sucesso,
            ao_erro=self._ao_atualizar_secao_secundaria_erro,
        )

    def _ao_atualizar_sugestao_reposicao_sucesso(self, itens):

        self.tabela_reposicao.setRowCount(len(itens))

        for linha, item in enumerate(itens):
            self.tabela_reposicao.setItem(
                linha, 0, QTableWidgetItem(item["produto"])
            )
            self.tabela_reposicao.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade_atual"]))
            )
            self.tabela_reposicao.setItem(
                linha, 2, QTableWidgetItem(str(item["estoque_minimo"]))
            )
            self.tabela_reposicao.setItem(
                linha, 3, QTableWidgetItem(str(item["quantidade_sugerida"]))
            )

    def _ao_atualizar_secao_secundaria_erro(self, erro):
        # secoes secundarias (curva ABC, comparativos, reposicao) -- um
        # erro numa delas nao deveria travar a aba inteira com um
        # QMessageBox bloqueante, so essa secao fica vazia (tabela ja
        # comeca vazia, entao nao precisa nem limpar).
        pass
