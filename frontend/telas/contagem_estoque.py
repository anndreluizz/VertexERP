from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QInputDialog,
    QTableWidgetItem,
)

from services.contagem_estoque_service import (
    contagem_aberta,
    abrir_contagem,
    registrar_item_contagem,
    finalizar_contagem,
    cancelar_contagem,
    listar_contagens,
)
from services.worker import rodar_em_thread, em_paralelo
from widgets.tables.standard_table import StandardTable
from design import tokens
from design.icons import icone_pixmap
from design.widgets import BotaoPrimario, Card


def _buscar_dados_contagem():
    """Roda na worker thread -- contagem aberta (se houver) e histórico,
    independentes entre si, disparadas em paralelo (mesmo padrao de
    transferencia_estoque.py)."""
    contagem, historico = em_paralelo(
        (contagem_aberta,), (listar_contagens,)
    )
    return contagem, historico


def _estilo_campo():
    return f"""
        QLineEdit {{
            border: 1px solid {tokens.BORDA};
            border-radius: {tokens.RADIUS_SM}px;
            padding: 0 10px;
            background: {tokens.CARD};
            color: {tokens.TEXTO};
        }}
        QLineEdit:focus {{
            border: 1px solid {tokens.PRIMARIA};
        }}
    """


def _estilo_botao(cor, cor_hover):
    return f"""
        QPushButton {{
            background:{cor};
            color:{tokens.TEXTO_CLARO};
            font-weight:bold;
            border-radius:{tokens.RADIUS_SM}px;
            padding:0 16px;
        }}
        QPushButton:hover {{
            background:{cor_hover};
        }}
        QPushButton:disabled {{
            background:{tokens.BORDA};
            color:{tokens.TEXTO_TERCIARIO};
        }}
    """


class ContagemEstoque(QWidget):

    def __init__(self):
        super().__init__()

        self.contagem = None
        self.itens = []
        self._carregando = False

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 24)
        layout.setSpacing(16)

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(12)

        icone_titulo = QLabel()
        icone_titulo.setFixedSize(36, 36)
        icone_titulo.setAlignment(Qt.AlignCenter)
        icone_titulo.setStyleSheet(
            f"background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_SM}px;"
        )
        icone_titulo.setPixmap(icone_pixmap("check", cor=tokens.PRIMARIA, tamanho=18))

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Contagem de Inventário")
        titulo.setStyleSheet(
            f"background:transparent; font-size:{tokens.TAMANHO_LG}px; "
            f"font-weight:800; color:{tokens.TEXTO};"
        )

        subtitulo = QLabel(
            "Confira o estoque físico com o que está no sistema. Ao "
            "finalizar, as diferenças viram ajustes de estoque automáticos."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(
            f"background:transparent; font-size:{tokens.TAMANHO_SM}px; "
            f"color:{tokens.TEXTO_TERCIARIO};"
        )

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        cabecalho.addWidget(icone_titulo, 0, Qt.AlignTop)
        cabecalho.addLayout(col_titulo, stretch=1)
        layout.addLayout(cabecalho)

        # ==========================================
        # PAINEL: ABRIR CONTAGEM (sem contagem aberta)
        # ==========================================
        self.painel_abrir = Card()
        abrir_externo = QVBoxLayout(self.painel_abrir)
        abrir_externo.setContentsMargins(20, 18, 20, 20)
        abrir_externo.setSpacing(4)

        lbl_nova = QLabel("Nova contagem")
        lbl_nova.setStyleSheet(
            f"background:transparent; font-size:{tokens.TAMANHO_MD}px; "
            f"font-weight:700; color:{tokens.TEXTO};"
        )
        abrir_externo.addWidget(lbl_nova)

        lbl_obs = QLabel(
            "Dê um nome pra identificar depois no histórico (opcional)."
        )
        lbl_obs.setStyleSheet(
            f"background:transparent; font-size:{tokens.TAMANHO_SM}px; "
            f"color:{tokens.TEXTO_SECUNDARIO};"
        )
        abrir_externo.addWidget(lbl_obs)
        abrir_externo.addSpacing(10)

        abrir_layout = QHBoxLayout()
        abrir_layout.setSpacing(12)

        self.observacao = QLineEdit()
        self.observacao.setPlaceholderText("Ex.: contagem mensal de outubro")
        self.observacao.setMinimumHeight(42)
        self.observacao.setStyleSheet(_estilo_campo())
        self.observacao.returnPressed.connect(self.abrir)
        abrir_layout.addWidget(self.observacao, stretch=1)

        self.bt_abrir = BotaoPrimario("Iniciar contagem", icone_nome="check")
        self.bt_abrir.setMinimumHeight(42)
        self.bt_abrir.clicked.connect(self.abrir)
        abrir_layout.addWidget(self.bt_abrir)

        abrir_externo.addLayout(abrir_layout)

        layout.addWidget(self.painel_abrir)

        # ==========================================
        # PAINEL: CONTAGEM ABERTA
        # ==========================================
        self.painel_ativo = QWidget()
        ativo_layout = QVBoxLayout(self.painel_ativo)
        ativo_layout.setContentsMargins(0, 0, 0, 0)
        ativo_layout.setSpacing(10)

        self.lbl_info_contagem = QLabel("")
        self.lbl_info_contagem.setWordWrap(True)
        self.lbl_info_contagem.setStyleSheet(
            f"background:transparent; font-size:{tokens.TAMANHO_SM}px; "
            f"color:{tokens.TEXTO};"
        )
        ativo_layout.addWidget(self.lbl_info_contagem)

        self.tabela_itens = StandardTable(
            ["Produto", "Qtd. Sistema", "Qtd. Contada", "Diferença"]
        )
        ativo_layout.addWidget(self.tabela_itens, stretch=1)

        acoes_layout = QHBoxLayout()
        acoes_layout.setSpacing(8)

        self.bt_registrar = QPushButton("Registrar Contagem")
        self.bt_registrar.setMinimumHeight(38)
        self.bt_registrar.setCursor(Qt.PointingHandCursor)
        self.bt_registrar.setStyleSheet(
            _estilo_botao(tokens.PRIMARIA, tokens.PRIMARIA_HOVER)
        )
        self.bt_registrar.clicked.connect(self.registrar_contagem)
        acoes_layout.addWidget(self.bt_registrar)

        self.bt_finalizar = QPushButton("Finalizar Contagem")
        self.bt_finalizar.setMinimumHeight(38)
        self.bt_finalizar.setCursor(Qt.PointingHandCursor)
        self.bt_finalizar.setStyleSheet(
            _estilo_botao(tokens.SUCESSO, tokens.SECUNDARIA_HOVER)
        )
        self.bt_finalizar.clicked.connect(self.finalizar)
        acoes_layout.addWidget(self.bt_finalizar)

        acoes_layout.addStretch()

        self.bt_cancelar = QPushButton("Cancelar Contagem")
        self.bt_cancelar.setMinimumHeight(38)
        self.bt_cancelar.setCursor(Qt.PointingHandCursor)
        self.bt_cancelar.setStyleSheet(
            _estilo_botao(tokens.ERRO, tokens.ERRO_HOVER)
        )
        self.bt_cancelar.clicked.connect(self.cancelar)
        acoes_layout.addWidget(self.bt_cancelar)

        ativo_layout.addLayout(acoes_layout)

        layout.addWidget(self.painel_ativo, stretch=1)

        # ==========================================
        # HISTÓRICO
        # ==========================================
        lbl_historico = QLabel("Histórico de contagens")
        lbl_historico.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO}; "
            f"font-size:{tokens.TAMANHO_MD}px; font-weight:700; "
            f"margin-top:6px;"
        )
        layout.addWidget(lbl_historico)

        self.tabela_historico = StandardTable(
            ["Aberta em", "Situação", "Encerrada em", "Observação"]
        )
        layout.addWidget(self.tabela_historico, stretch=1)

        self.lbl_historico_vazio = QLabel(
            "Nenhuma contagem feita ainda. A primeira aparece aqui quando "
            "for finalizada ou cancelada."
        )
        self.lbl_historico_vazio.setAlignment(Qt.AlignCenter)
        self.lbl_historico_vazio.setStyleSheet(
            f"background:{tokens.CARD}; border:1px dashed {tokens.BORDA}; "
            f"border-radius:{tokens.RADIUS_MD}px; padding:28px; "
            f"color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_SM}px;"
        )
        self.lbl_historico_vazio.setVisible(False)
        layout.addWidget(self.lbl_historico_vazio)

        # quem fica com a altura que sobra: o painel da contagem aberta
        # (stretch dele) ou a tabela do histórico; quando nenhum dos dois
        # está na tela, este enchimento -- senão o Qt espalhava a sobra
        # como vãos enormes entre os blocos
        self._enchimento = QWidget()
        self._enchimento.setStyleSheet("background:transparent;")
        layout.addWidget(self._enchimento, stretch=1)

        self.carregar()

    # ==========================================
    # CARREGAR
    # ==========================================
    def carregar(self):
        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            _buscar_dados_contagem,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_abrir.setEnabled(not carregando)
        self.bt_registrar.setEnabled(not carregando)
        self.bt_finalizar.setEnabled(not carregando)
        self.bt_cancelar.setEnabled(not carregando)

    def _ao_carregar_sucesso(self, resultado):
        self.contagem, historico = resultado

        if self.contagem is None:
            self.itens = []
            self.painel_abrir.setVisible(True)
            self.painel_ativo.setVisible(False)
            # sem contagem aberta o histórico é o conteúdo principal
            self.tabela_historico.setMaximumHeight(16777215)
        else:
            self.tabela_historico.setMaximumHeight(200)
            self.itens = self.contagem["itens"]
            self.painel_abrir.setVisible(False)
            self.painel_ativo.setVisible(True)
            self._preencher_info()
            self._preencher_itens()

        self._preencher_historico(historico)

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar a contagem.\n{erro}"
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def _preencher_info(self):
        criado_em = datetime.fromisoformat(
            self.contagem["criado_em"]
        ).strftime("%d/%m/%Y %H:%M")

        divergentes = sum(
            1
            for i in self.itens
            if i["quantidade_contada"] is not None
            and i["quantidade_contada"] != i["quantidade_sistema"]
        )
        contados = sum(
            1 for i in self.itens if i["quantidade_contada"] is not None
        )

        self.lbl_info_contagem.setText(
            f"Contagem #{self.contagem['id']} aberta em {criado_em} · "
            f"{contados}/{len(self.itens)} produtos contados, "
            f"{divergentes} com diferença."
        )

    def _preencher_itens(self):
        self.tabela_itens.setRowCount(len(self.itens))

        for linha, item in enumerate(self.itens):
            contada = item["quantidade_contada"]
            diferenca = "" if contada is None else str(
                contada - item["quantidade_sistema"]
            )

            self.tabela_itens.setItem(
                linha, 0, QTableWidgetItem(item.get("produto_nome") or "")
            )
            self.tabela_itens.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade_sistema"]))
            )
            self.tabela_itens.setItem(
                linha, 2,
                QTableWidgetItem("" if contada is None else str(contada)),
            )
            celula_diferenca = QTableWidgetItem(diferenca)
            # falta (negativo) em vermelho, sobra em verde -- o que o
            # dono precisa ver antes de finalizar
            if contada is not None and contada != item["quantidade_sistema"]:
                celula_diferenca.setForeground(QColor(
                    tokens.ERRO if contada < item["quantidade_sistema"] else tokens.SUCESSO
                ))
                fonte_dif = celula_diferenca.font()
                fonte_dif.setBold(True)
                celula_diferenca.setFont(fonte_dif)
            self.tabela_itens.setItem(linha, 3, celula_diferenca)

    def _preencher_historico(self, historico):
        self.tabela_historico.setRowCount(len(historico))
        self.tabela_historico.setVisible(bool(historico))
        self.lbl_historico_vazio.setVisible(not historico)
        self._enchimento.setVisible(not historico and self.contagem is None)

        for linha, c in enumerate(historico):
            criado_em = datetime.fromisoformat(c["criado_em"]).strftime(
                "%d/%m/%Y %H:%M"
            )
            encerrado_em = (
                datetime.fromisoformat(c["finalizado_em"]).strftime(
                    "%d/%m/%Y %H:%M"
                )
                if c.get("finalizado_em")
                else "—"
            )

            self.tabela_historico.setItem(linha, 0, QTableWidgetItem(criado_em))
            self.tabela_historico.setItem(
                linha, 1, QTableWidgetItem(str(c["status"]).capitalize())
            )
            self.tabela_historico.setItem(
                linha, 2, QTableWidgetItem(encerrado_em)
            )
            self.tabela_historico.setItem(
                linha, 3, QTableWidgetItem(c.get("observacao") or "")
            )

    # ==========================================
    # ABRIR
    # ==========================================
    def abrir(self):
        self.bt_abrir.setEnabled(False)

        rodar_em_thread(
            self,
            abrir_contagem,
            self.observacao.text() or None,
            ao_sucesso=self._ao_abrir_sucesso,
            ao_erro=self._ao_abrir_erro,
            ao_finalizar=self._ao_abrir_finalizado,
        )

    def _ao_abrir_sucesso(self, response):
        if response.status_code == 201:
            self.observacao.clear()
            self.carregar()
        else:
            self._exibir_erro(response)

    def _ao_abrir_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_abrir_finalizado(self):
        if not self._carregando:
            self.bt_abrir.setEnabled(True)

    # ==========================================
    # REGISTRAR CONTAGEM DE UM ITEM
    # ==========================================
    def registrar_contagem(self):
        linha = self.tabela_itens.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um produto na tabela.")
            return

        item = self.itens[linha]
        valor_atual = item["quantidade_contada"]
        if valor_atual is None:
            valor_atual = item["quantidade_sistema"]

        quantidade, ok = QInputDialog.getInt(
            self,
            "Registrar contagem",
            f"Quantidade contada de \"{item.get('produto_nome') or item['produto_id']}\":",
            valor_atual,
            0,
            999999,
        )

        if not ok:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            registrar_item_contagem,
            self.contagem["id"],
            item["id"],
            quantidade,
            ao_sucesso=self._ao_registrar_item_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_registrar_item_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # FINALIZAR
    # ==========================================
    def finalizar(self):
        if self.contagem is None:
            return

        resposta = QMessageBox.question(
            self,
            "Finalizar contagem",
            "Finalizar essa contagem? Produtos com diferença entre a "
            "quantidade contada e o sistema terão o estoque ajustado "
            "automaticamente. Produtos não contados ficam como estão.",
        )

        if resposta != QMessageBox.Yes:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            finalizar_contagem,
            self.contagem["id"],
            ao_sucesso=self._ao_finalizar_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_finalizar_sucesso(self, response):
        if response.status_code == 200:
            QMessageBox.information(
                self, "Sucesso", "Contagem finalizada e estoque ajustado."
            )
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # CANCELAR
    # ==========================================
    def cancelar(self):
        if self.contagem is None:
            return

        resposta = QMessageBox.question(
            self,
            "Cancelar contagem",
            "Cancelar essa contagem? Nenhum ajuste de estoque será feito "
            "e as quantidades contadas até agora serão descartadas.",
        )

        if resposta != QMessageBox.Yes:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            cancelar_contagem,
            self.contagem["id"],
            ao_sucesso=self._ao_cancelar_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_cancelar_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # HELPERS COMPARTILHADOS
    # ==========================================
    def _ao_mutacao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutacao_finalizada(self):
        if not self._carregando:
            self._definir_controles_carregando(False)

    def _exibir_erro(self, response):
        try:
            erro = response.json()["detail"]
        except Exception:
            erro = response.text

        QMessageBox.critical(self, "Erro", erro)
