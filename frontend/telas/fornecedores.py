from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import Avatar, Badge, BotaoPrimario, BotaoSecundario, CampoTexto
from services.fornecedor_service import listar_fornecedores, excluir_fornecedor
from services.worker import rodar_em_thread
from services import api
from widgets.estado_async import PainelErro
from telas.cadastro_fornecedor import CadastroFornecedorDialog
from telas.importar_nfe import ImportarNFeDialog


# excluir é soft-delete (vira inativo) -- por isso o padrão é "Ativos":
# quem foi excluído some da lista, como a mensagem de exclusão promete
FILTROS_STATUS = [
    ("Ativos", "ATIVOS", "check"),
    ("Inativos", "INATIVOS", "eye-off"),
    ("Todos", "TODOS", "truck"),
]

COL_FORNECEDOR, COL_CNPJ, COL_CONTATO, COL_CIDADE, COL_MARGEM, COL_STATUS, COL_ACOES = range(7)


def formatar_cnpj(cnpj):
    digitos = "".join(c for c in (cnpj or "") if c.isdigit())
    if len(digitos) != 14:
        return cnpj or ""
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"


def formatar_margem(margem):
    margem = float(margem or 0)
    if margem == int(margem):
        return f"{margem:.0f}%"
    return f"{margem:.2f}%".replace(".", ",")


def _nome_exibido(f):
    return f.get("nome_fantasia") or f.get("razao_social") or ""


def _rotulo(texto, tamanho, cor=None, peso=400):
    lbl = QLabel(texto)
    lbl.setStyleSheet(f"""
        background:transparent; font-size:{tamanho}px;
        font-weight:{peso}; color:{cor or tokens.TEXTO};
    """)
    return lbl


class Fornecedores(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.fornecedores = []
        self.fornecedores_exibidos = []
        self.filtro_status = "ATIVOS"
        self.botoes_status = {}
        self._carregando = False
        self._pode_excluir = api.usuario_tem_permissao("fornecedores.excluir")

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(12)

        self.bt_voltar = QPushButton()
        self.bt_voltar.setFixedSize(36, 36)
        self.bt_voltar.setCursor(Qt.PointingHandCursor)
        self.bt_voltar.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        self.bt_voltar.setToolTip("Voltar")
        self.bt_voltar.setAccessibleName("Voltar")
        self.bt_voltar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        icone_titulo = QLabel()
        icone_titulo.setFixedSize(36, 36)
        icone_titulo.setAlignment(Qt.AlignCenter)
        icone_titulo.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_SM}px;
        """)
        icone_titulo.setPixmap(icone_pixmap("truck", cor=tokens.PRIMARIA, tamanho=18))

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Fornecedores")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            "Cadastre fornecedores e importe notas fiscais (NF-e) pra "
            "dar entrada em produtos e estoque em lote."
        )
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        # seta pra baixo: a nota "entra" no sistema (mesmo ícone do
        # Importar de Produtos; antes era arrow-up, cara de exportar)
        self.bt_importar_nfe = BotaoSecundario("Importar NF-e", icone_nome="arrow-down")
        self.bt_importar_nfe.clicked.connect(self.abrir_importar_nfe)

        self.bt_novo = BotaoPrimario("Novo Fornecedor", icone_nome="plus")
        self.bt_novo.clicked.connect(self.novo_fornecedor)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addWidget(icone_titulo)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_importar_nfe)
        cabecalho.addWidget(self.bt_novo)

        layout.addLayout(cabecalho)

        # ======================
        # BUSCA + FILTROS DE STATUS (pílulas no estilo de Produtos)
        # ======================

        barra = QHBoxLayout()
        barra.setSpacing(8)

        self.pesquisa = CampoTexto("Buscar por nome, CNPJ, cidade, e-mail ou telefone...")
        self.pesquisa.setMinimumWidth(260)
        self.pesquisa.textChanged.connect(self.filtrar)
        barra.addWidget(self.pesquisa, stretch=1)
        barra.addSpacing(8)

        for rotulo, chave, _icone in FILTROS_STATUS:
            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(36)
            bt.clicked.connect(lambda checked=False, c=chave: self.selecionar_status(c))
            self.botoes_status[chave] = bt
            barra.addWidget(bt)

        layout.addLayout(barra)

        # ======================
        # TABELA
        # ======================

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(7)
        self.tabela.setHorizontalHeaderLabels(
            ["Fornecedor", "CNPJ", "Contato", "Cidade", "Margem", "Status", "Ações"]
        )
        cab = self.tabela.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(COL_FORNECEDOR, QHeaderView.Stretch)
        # colunas feitas de widget (contato, selo, botões) não entram no
        # ResizeToContents -- largura fixa pra não cortar o selo
        for coluna, largura in ((COL_CONTATO, 250), (COL_STATUS, 100), (COL_ACOES, 90)):
            cab.setSectionResizeMode(coluna, QHeaderView.Fixed)
            self.tabela.setColumnWidth(coluna, largura)
        cab.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.tabela.horizontalHeaderItem(COL_MARGEM).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.tabela.horizontalHeaderItem(COL_STATUS).setTextAlignment(Qt.AlignCenter)
        self.tabela.horizontalHeaderItem(COL_ACOES).setTextAlignment(Qt.AlignCenter)

        self.tabela.verticalHeader().setDefaultSectionSize(60)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setShowGrid(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                alternate-background-color: {tokens.FUNDO};
                font-size: {tokens.TAMANHO_BASE}px;
            }}
            QTableWidget::item {{ padding: 0 8px; }}
            QTableWidget::item:selected {{
                background: {tokens.PRIMARIA_CLARA};
                color: {tokens.TEXTO};
            }}
            QHeaderView::section {{
                background: {tokens.CARD};
                color: {tokens.TEXTO_SECUNDARIO};
                font-weight: 700;
                font-size: {tokens.TAMANHO_XS}px;
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
        """)
        self.tabela.doubleClicked.connect(
            lambda index: self.editar_selecionado() if index.column() != COL_ACOES else None
        )
        layout.addWidget(self.tabela, stretch=1)

        self.painel_erro = PainelErro()
        self.painel_erro.tentar_novamente.connect(self.carregar)
        self.painel_erro.hide()
        layout.addWidget(self.painel_erro)

        self.lbl_vazio = QLabel("")
        self.lbl_vazio.setAlignment(Qt.AlignCenter)
        self.lbl_vazio.setWordWrap(True)
        self.lbl_vazio.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_MD}px; padding:32px;
        """)
        self.lbl_vazio.hide()
        layout.addWidget(self.lbl_vazio, stretch=1)

        # ======================
        # RODAPÉ (Editar/Excluir foram pra própria linha)
        # ======================

        rodape = QHBoxLayout()

        dicas = QLabel("Ctrl+N novo  ·  F5 atualizar  ·  Delete excluir  ·  duplo clique edita")
        dicas.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        self.lbl_resumo = QLabel("")
        self.lbl_resumo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        self.bt_atualizar = BotaoSecundario("Atualizar", icone_nome="refresh-cw")
        self.bt_atualizar.clicked.connect(self.carregar)

        rodape.addWidget(dicas)
        rodape.addStretch()
        rodape.addWidget(self.lbl_resumo)
        rodape.addSpacing(12)
        rodape.addWidget(self.bt_atualizar)

        layout.addLayout(rodape)

        QShortcut(QKeySequence("Ctrl+N"), self, self.novo_fornecedor)
        QShortcut(QKeySequence("F5"), self, self.carregar)
        QShortcut(QKeySequence("Delete"), self, self.excluir_selecionado)

        self._marcar_status_selecionado(self.filtro_status)

    # ======================
    # CARREGAMENTO
    # ======================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)
        self.lbl_resumo.setText("Carregando...")

        rodar_em_thread(
            self,
            listar_fornecedores,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_novo.setEnabled(not carregando)
        self.bt_importar_nfe.setEnabled(not carregando)
        self.bt_atualizar.setEnabled(not carregando)

    def _ao_carregar_sucesso(self, fornecedores):
        try:
            self.fornecedores = sorted(fornecedores, key=lambda f: _nome_exibido(f).casefold())
            self.painel_erro.hide()
            self._atualizar_contagens()
            self.filtrar()
        except Exception as erro:
            self._ao_carregar_erro(erro)

    def _ao_carregar_erro(self, erro):
        self.tabela.setRowCount(0)
        self.tabela.hide()
        self.lbl_vazio.hide()
        self.painel_erro.definir_mensagem(
            f"Não foi possível carregar os fornecedores.\n{erro}"
        )
        self.painel_erro.show()
        self.lbl_resumo.setText("Falha ao carregar")

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    # ======================
    # FILTROS
    # ======================

    def selecionar_status(self, chave):
        self._marcar_status_selecionado(chave)
        self.filtrar()

    def _marcar_status_selecionado(self, chave):

        self.filtro_status = chave
        icones = {c: i for _r, c, i in FILTROS_STATUS}

        for k, botao in self.botoes_status.items():
            selecionado = k == chave
            botao.setChecked(selecionado)
            botao.setIcon(icone(
                icones[k],
                cor=tokens.PRIMARIA if selecionado else tokens.TEXTO_SECUNDARIO,
                tamanho=14,
            ))
            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.PRIMARIA_CLARA if selecionado else tokens.CARD};
                    color: {tokens.PRIMARIA if selecionado else tokens.TEXTO_SECUNDARIO};
                    border-radius: 18px;
                    border: 1px solid {tokens.PRIMARIA_CLARA if selecionado else tokens.BORDA};
                    font-weight: {700 if selecionado else 600};
                    font-size: {tokens.TAMANHO_SM}px;
                    padding: 0 14px;
                }}
                QPushButton:hover {{
                    background: {tokens.PRIMARIA_CLARA if selecionado else tokens.FUNDO};
                }}
            """)

    def _atualizar_contagens(self):
        ativos = sum(1 for f in self.fornecedores if f.get("ativo", True))
        contagem = {
            "ATIVOS": ativos,
            "INATIVOS": len(self.fornecedores) - ativos,
            "TODOS": len(self.fornecedores),
        }
        for rotulo, chave, _i in FILTROS_STATUS:
            self.botoes_status[chave].setText(f"{rotulo}  {contagem[chave]}")

    def filtrar(self):

        termo = self.pesquisa.text().strip().casefold()
        termo_digitos = "".join(c for c in termo if c.isdigit())

        def passa(f):
            ativo = f.get("ativo", True)
            if self.filtro_status == "ATIVOS" and not ativo:
                return False
            if self.filtro_status == "INATIVOS" and ativo:
                return False
            if not termo:
                return True
            campos = " ".join(str(f.get(k) or "") for k in (
                "razao_social", "nome_fantasia", "cidade", "estado", "email", "telefone",
            )).casefold()
            if termo in campos:
                return True
            # CNPJ/telefone digitados com ou sem pontuação
            return bool(termo_digitos) and termo_digitos in "".join(
                c for c in f"{f.get('cnpj', '')} {f.get('telefone') or ''}" if c.isdigit()
            )

        exibidos = [f for f in self.fornecedores if passa(f)]
        self.preencher_tabela(exibidos)

        total = len(self.fornecedores)
        self.lbl_resumo.setText(
            f"{len(exibidos)} de {total} fornecedor{'es' if total != 1 else ''}"
        )

        if exibidos or self.painel_erro.isVisible():
            self.lbl_vazio.hide()
            self.tabela.setVisible(not self.painel_erro.isVisible())
            return

        self.tabela.hide()
        if not self.fornecedores:
            self.lbl_vazio.setText(
                "Nenhum fornecedor cadastrado ainda.\n"
                "Clique em Novo Fornecedor ou importe uma NF-e — o fornecedor "
                "da nota é cadastrado junto."
            )
        else:
            self.lbl_vazio.setText("Nenhum fornecedor encontrado com esse filtro.")
        self.lbl_vazio.show()

    # ======================
    # TABELA
    # ======================

    def preencher_tabela(self, fornecedores):

        self.fornecedores_exibidos = fornecedores

        # zera antes de repopular -- mesmo motivo de Produtos: widget de
        # célula por cima de widget antigo deixava linhas fantasmas
        self.tabela.setRowCount(0)
        self.tabela.setRowCount(len(fornecedores))

        cinza = QColor(tokens.TEXTO_TERCIARIO)

        for linha, f in enumerate(fornecedores):

            # item vazio por baixo dos widgets: é ele que recebe seleção e duplo clique
            self.tabela.setItem(linha, COL_FORNECEDOR, QTableWidgetItem())
            self.tabela.setCellWidget(linha, COL_FORNECEDOR, self._widget_nome(f))

            self.tabela.setItem(linha, COL_CNPJ, QTableWidgetItem(formatar_cnpj(f.get("cnpj"))))

            self.tabela.setItem(linha, COL_CONTATO, QTableWidgetItem())
            self.tabela.setCellWidget(linha, COL_CONTATO, self._widget_contato(f))

            cidade = f.get("cidade") or ""
            if cidade and f.get("estado"):
                cidade = f"{cidade} – {f['estado']}"
            item_cidade = QTableWidgetItem(cidade or "—")
            if not cidade:
                item_cidade.setForeground(cinza)
            self.tabela.setItem(linha, COL_CIDADE, item_cidade)

            item_margem = QTableWidgetItem(formatar_margem(f.get("margem_padrao")))
            item_margem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            fonte = item_margem.font()
            fonte.setBold(True)
            item_margem.setFont(fonte)
            self.tabela.setItem(linha, COL_MARGEM, item_margem)

            ativo = f.get("ativo", True)
            self.tabela.setCellWidget(linha, COL_STATUS, self._centralizado(
                Badge("Ativo" if ativo else "Inativo", "sucesso" if ativo else "neutro")
            ))

            self.tabela.setCellWidget(linha, COL_ACOES, self._widget_acoes(f))

    def _widget_nome(self, f):

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(12)

        nome = _nome_exibido(f)
        layout.addWidget(Avatar(nome, tamanho=34))

        col = QVBoxLayout()
        col.setSpacing(1)
        col.setAlignment(Qt.AlignVCenter)
        col.addWidget(_rotulo(nome, tokens.TAMANHO_BASE, peso=700))
        # razão social embaixo só quando o nome de cima é o fantasia
        if f.get("nome_fantasia"):
            col.addWidget(_rotulo(f.get("razao_social", ""), tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO))
        layout.addLayout(col, stretch=1)

        return container

    def _widget_contato(self, f):

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(1)
        layout.setAlignment(Qt.AlignVCenter)

        telefone, email = f.get("telefone"), f.get("email")
        if not telefone and not email:
            layout.addWidget(_rotulo("Sem contato", tokens.TAMANHO_SM, tokens.TEXTO_TERCIARIO))
        if telefone:
            layout.addWidget(_rotulo(telefone, tokens.TAMANHO_SM))
        if email and telefone:
            layout.addWidget(_rotulo(email, tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO))
        elif email:
            layout.addWidget(_rotulo(email, tokens.TAMANHO_SM))

        return container

    def _centralizado(self, widget):
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(widget)
        return container

    def _widget_acoes(self, f):

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        bt_editar = QPushButton()
        bt_editar.setFixedSize(28, 28)
        bt_editar.setCursor(Qt.PointingHandCursor)
        bt_editar.setToolTip("Editar fornecedor")
        bt_editar.setAccessibleName("Editar fornecedor")
        bt_editar.setIcon(icone("edit-2", cor=tokens.PRIMARIA, tamanho=15))
        bt_editar.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA}; }}
        """)
        bt_editar.clicked.connect(lambda checked=False, x=f: self._editar(x))
        layout.addWidget(bt_editar)

        # inativo já está "excluído" (soft-delete): sem botão de excluir
        if self._pode_excluir and f.get("ativo", True):
            bt_excluir = QPushButton()
            bt_excluir.setFixedSize(28, 28)
            bt_excluir.setCursor(Qt.PointingHandCursor)
            bt_excluir.setToolTip("Excluir fornecedor")
            bt_excluir.setAccessibleName("Excluir fornecedor")
            bt_excluir.setIcon(icone("trash-2", cor=tokens.ERRO, tamanho=15))
            bt_excluir.setStyleSheet(f"""
                QPushButton {{ background:transparent; border:none; border-radius:6px; }}
                QPushButton:hover {{ background:{tokens.ERRO_CLARO}; }}
            """)
            bt_excluir.clicked.connect(lambda checked=False, x=f: self._excluir(x))
            layout.addWidget(bt_excluir)

        return container

    # ======================
    # AÇÕES
    # ======================

    def _fornecedor_selecionado(self):

        linha = self.tabela.currentRow()

        if linha < 0 or linha >= len(self.fornecedores_exibidos):
            QMessageBox.warning(self, "Aviso", "Selecione um fornecedor.")
            return None

        return self.fornecedores_exibidos[linha]

    def novo_fornecedor(self):
        dialog = CadastroFornecedorDialog(parent=self)
        if dialog.exec():
            self.carregar()

    def editar_selecionado(self):
        fornecedor = self._fornecedor_selecionado()
        if fornecedor is not None:
            self._editar(fornecedor)

    def _editar(self, fornecedor):
        dialog = CadastroFornecedorDialog(fornecedor=fornecedor, parent=self)
        if dialog.exec():
            self.carregar()

    def excluir_selecionado(self):
        if not self._pode_excluir:
            return
        fornecedor = self._fornecedor_selecionado()
        if fornecedor is not None and fornecedor.get("ativo", True):
            self._excluir(fornecedor)

    def _excluir(self, fornecedor):

        resposta = QMessageBox.question(
            self,
            "Excluir fornecedor",
            f"Excluir o fornecedor \"{fornecedor.get('razao_social')}\"?\n\n"
            "O histórico de compras dele é mantido -- ele só deixa de "
            "aparecer nas listas pra novas compras/importações.",
        )

        if resposta != QMessageBox.Yes:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            excluir_fornecedor,
            fornecedor["id"],
            ao_sucesso=self._ao_excluir_sucesso,
            ao_erro=self._ao_excluir_erro,
            ao_finalizar=lambda: self._definir_controles_carregando(False),
        )

    def _ao_excluir_sucesso(self, response):
        if response.status_code == 200:
            # adiado pro próximo ciclo: o "finalizado" desta thread ainda
            # vai rodar e reabilitaria os botões no meio do carregamento
            QTimer.singleShot(0, self.carregar)
        else:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_excluir_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível excluir o fornecedor.\n{erro}")

    def abrir_importar_nfe(self):
        dialog = ImportarNFeDialog(parent=self)
        if dialog.exec():
            self.carregar()
