from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import (
    Badge, BotaoSucesso, CampoTexto, DialogoPadrao, PilhaPaginas,
    campo_rotulado, estilo_botao_forma, estilo_checkbox, tabela_lista,
    titulo_secao,
)
from services.fornecedor_service import importar_nfe_preview
from services.categoria_service import listar_categorias
from services.compra_service import importar_nfe_confirmar
from services.worker import rodar_em_thread
from utils.formatacao import formatar_moeda

# (valor, rótulo, ícone) -- mesmas cores das outras telas de pagamento
_FORMAS_PAGAMENTO = [
    ("DINHEIRO", "Dinheiro", "dollar-sign"),
    ("PIX", "PIX", "refresh-cw"),
    ("DEBITO", "Débito", "credit-card"),
    ("CREDITO", "Crédito", "credit-card"),
    ("BOLETO", "Boleto", "file-text"),
    ("PRAZO", "A prazo", "calendar"),
]

# indices das colunas da tabela de revisao
_COL_CODIGO = 0
_COL_DESCRICAO = 1
_COL_STATUS = 2
_COL_QUANTIDADE = 3
_COL_CUSTO = 4
_COL_PRECO_ATUAL = 5
_COL_PRECO_VENDA = 6
_COL_MARGEM = 7

_TEXTO_AREA_SOLTAR = (
    "O sistema lê a nota e mostra tudo pra você conferir.\n"
    "Nada é gravado até você clicar em Importar nota."
)


def _numero(texto):
    """Aceita '22,40', '22.40' e '1.234,56'; None se não for número."""
    texto = (texto or "").replace("R$", "").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _fmt(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_cnpj(cnpj):
    digitos = "".join(c for c in str(cnpj or "") if c.isdigit())
    if len(digitos) != 14:
        return cnpj or ""
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"


class ImportarNFeDialog(DialogoPadrao):
    """Sobe um XML de NF-e, mostra o que foi extraido/casado com produtos
    ja cadastrados numa tabela revisavel, e so' grava de verdade
    (fornecedor + produtos + compra + estoque) quando o usuario confirma.

    Produto ja cadastrado mantem o preco de venda atual por padrao, e o
    backend so' troca esse preco com atualizar_preco_venda=True -- antes
    a sugestao custo x margem ia pra todo mundo, e margem 0% derrubava
    o preco da loja pro preco de custo."""

    def __init__(self, parent=None):

        super().__init__(
            "Importar NF-e", "Entrada de mercadoria pelo XML da nota fiscal",
            "download", tokens.SECUNDARIA, tokens.SUCESSO_CLARO,
            largura=DialogoPadrao.GRANDE, parent=parent,
        )
        # alta o bastante pra tabela + pagamento sem rolar, mas sem
        # passar de 90% da tela (telas de 900px de altura)
        from PySide6.QtWidgets import QApplication
        tela = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        self.resize(980, min(820, int(tela.height() * 0.9)))
        self.setAcceptDrops(True)

        self.preview = None
        self.itens_originais = []
        self.forma_pagamento = "BOLETO"
        self._nome_arquivo = "XML"
        self._total_nota = 0.0

        self.paginas = PilhaPaginas()
        self.pagina_arquivo = self._criar_pagina_arquivo()
        self.pagina_revisao = self._criar_pagina_revisao()
        self.paginas.addWidget(self.pagina_arquivo)
        self.paginas.addWidget(self.pagina_revisao)
        self.corpo.addWidget(self.paginas, 1)

        self.lbl_total_rodape = QLabel("")
        self.lbl_total_rodape.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_MD}px;
            font-weight:700; color:{tokens.TEXTO_SECUNDARIO};
        """)
        self.rodape.addWidget(self.lbl_total_rodape)

        self.bt_confirmar = BotaoSucesso("Importar nota", icone_nome="check")
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.setEnabled(False)
        self.bt_confirmar.clicked.connect(self.confirmar)
        self.bt_cancelar = self.definir_botoes(self.bt_confirmar)

    # ======================
    # PÁGINA 1 · ARQUIVO
    # ======================

    def _criar_pagina_arquivo(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)

        self.area_soltar = QFrame()
        self.area_soltar.setObjectName("areaSoltar")
        self._pintar_area_soltar(False)

        area = QVBoxLayout(self.area_soltar)
        area.setContentsMargins(40, 40, 40, 40)
        area.setSpacing(12)
        area.addStretch()

        icone_xml = QLabel()
        icone_xml.setAlignment(Qt.AlignCenter)
        icone_xml.setStyleSheet("background:transparent;")
        icone_xml.setPixmap(icone_pixmap("file-text", cor=tokens.SECUNDARIA, tamanho=44))
        area.addWidget(icone_xml)

        titulo = QLabel("Arraste o XML da NF-e pra cá")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        area.addWidget(titulo)

        ou = QLabel("ou")
        ou.setAlignment(Qt.AlignCenter)
        ou.setStyleSheet(f"background:transparent; color:{tokens.TEXTO_TERCIARIO};")
        area.addWidget(ou)

        self.bt_selecionar = BotaoSucesso("Escolher arquivo XML", icone_nome="download")
        self.bt_selecionar.setAutoDefault(False)
        self.bt_selecionar.setMinimumWidth(240)
        self.bt_selecionar.clicked.connect(self.selecionar_arquivo)
        linha_bt = QHBoxLayout()
        linha_bt.addStretch()
        linha_bt.addWidget(self.bt_selecionar)
        linha_bt.addStretch()
        area.addLayout(linha_bt)

        self.lbl_arquivo = QLabel(_TEXTO_AREA_SOLTAR)
        self.lbl_arquivo.setAlignment(Qt.AlignCenter)
        self.lbl_arquivo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px; color:{tokens.TEXTO_TERCIARIO};
        """)
        area.addWidget(self.lbl_arquivo)
        area.addStretch()

        layout.addWidget(self.area_soltar, 1)
        return pagina

    def _pintar_area_soltar(self, ativo):
        cor = tokens.SECUNDARIA if ativo else tokens.BORDA_FORTE
        fundo = tokens.SUCESSO_CLARO if ativo else tokens.FUNDO
        self.area_soltar.setStyleSheet(f"""
            QFrame#areaSoltar {{
                background:{fundo}; border:2px dashed {cor};
                border-radius:{tokens.RADIUS_LG}px;
            }}
        """)

    # arrastar e soltar o XML em qualquer lugar da janela
    def _xml_do_evento(self, event):
        dados = event.mimeData()
        if not dados.hasUrls():
            return None
        for url in dados.urls():
            caminho = url.toLocalFile()
            if caminho.lower().endswith(".xml"):
                return caminho
        return None

    def dragEnterEvent(self, event):
        if self._xml_do_evento(event):
            event.acceptProposedAction()
            self._pintar_area_soltar(True)

    def dragLeaveEvent(self, event):
        self._pintar_area_soltar(False)

    def dropEvent(self, event):
        self._pintar_area_soltar(False)
        caminho = self._xml_do_evento(event)
        if caminho:
            event.acceptProposedAction()
            self.carregar_arquivo(caminho)

    # ======================
    # PÁGINA 2 · REVISÃO
    # ======================

    def _criar_cartao_fornecedor(self):

        cartao = QFrame()
        cartao.setObjectName("cartaoFornecedor")
        cartao.setStyleSheet(f"""
            QFrame#cartaoFornecedor {{
                background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_MD}px;
            }}
        """)
        linha = QHBoxLayout(cartao)
        linha.setContentsMargins(16, 12, 16, 12)
        linha.setSpacing(14)

        icone_forn = QLabel()
        icone_forn.setFixedSize(44, 44)
        icone_forn.setAlignment(Qt.AlignCenter)
        icone_forn.setStyleSheet(f"background:{tokens.CARD}; border-radius:{tokens.RADIUS_MD}px;")
        icone_forn.setPixmap(icone_pixmap("truck", cor=tokens.PRIMARIA, tamanho=20))
        linha.addWidget(icone_forn)

        col = QVBoxLayout()
        col.setSpacing(4)
        linha_nome = QHBoxLayout()
        linha_nome.setSpacing(8)
        self.fornecedor_razao_social = CampoTexto("Razão social do fornecedor")
        self.fornecedor_razao_social.setMinimumHeight(38)
        self.badge_fornecedor = Badge("", "neutro")
        linha_nome.addWidget(self.fornecedor_razao_social, 1)
        linha_nome.addWidget(self.badge_fornecedor)
        self.lbl_fornecedor_cnpj = QLabel("")
        self.lbl_fornecedor_cnpj.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO}; font-size:{tokens.TAMANHO_SM}px;
        """)
        col.addLayout(linha_nome)
        col.addWidget(self.lbl_fornecedor_cnpj)
        linha.addLayout(col, 1)

        self.fornecedor_margem = QDoubleSpinBox()
        self.fornecedor_margem.setRange(0, 999)
        self.fornecedor_margem.setDecimals(1)
        self.fornecedor_margem.setSuffix(" %")
        self.fornecedor_margem.setMinimumHeight(38)
        self.fornecedor_margem.setMinimumWidth(110)
        self.fornecedor_margem.setStyleSheet(f"""
            QDoubleSpinBox {{
                border:1.5px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:0 10px; font-size:{tokens.TAMANHO_MD}px; font-weight:700;
                color:{tokens.TEXTO}; background:{tokens.CARD};
            }}
            QDoubleSpinBox:focus {{ border-color:{tokens.PRIMARIA}; }}
        """)
        self.fornecedor_margem.valueChanged.connect(self._recalcular_precos_sugeridos)
        linha.addWidget(campo_rotulado("Margem padrão", self.fornecedor_margem))

        bt_trocar = QPushButton("Trocar arquivo")
        bt_trocar.setCursor(Qt.PointingHandCursor)
        bt_trocar.setAutoDefault(False)
        bt_trocar.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; color:{tokens.PRIMARIA};
                font-weight:700; font-size:{tokens.TAMANHO_SM}px; }}
            QPushButton:hover {{ text-decoration:underline; }}
        """)
        bt_trocar.clicked.connect(self.selecionar_arquivo)
        linha.addWidget(bt_trocar, 0, Qt.AlignTop)

        return cartao

    def _criar_kpis(self):

        linha_kpi = QHBoxLayout()
        linha_kpi.setSpacing(10)
        self.kpi = {}
        for chave, titulo in (
            ("itens", "Itens na nota"), ("novos", "Produtos novos"),
            ("existentes", "Já cadastrados"), ("total", "Total da nota"),
        ):
            bloco = QFrame()
            bloco.setObjectName("kpiNota")
            bloco.setStyleSheet(f"""
                QFrame#kpiNota {{
                    background:{tokens.CARD}; border:1.5px solid {tokens.BORDA};
                    border-radius:{tokens.RADIUS_MD}px;
                }}
            """)
            kl = QVBoxLayout(bloco)
            kl.setContentsMargins(14, 8, 14, 8)
            kl.setSpacing(2)
            lbl_t = QLabel(titulo.upper())
            lbl_t.setStyleSheet(f"""
                background:transparent; font-size:{tokens.TAMANHO_XS}px; font-weight:800;
                color:{tokens.TEXTO_SECUNDARIO}; letter-spacing:0.5px;
            """)
            lbl_v = QLabel("0")
            lbl_v.setStyleSheet(f"""
                background:transparent; font-size:{tokens.TAMANHO_LG}px; font-weight:800;
                color:{tokens.PRIMARIA if chave == 'total' else tokens.TEXTO};
            """)
            kl.addWidget(lbl_t)
            kl.addWidget(lbl_v)
            linha_kpi.addWidget(bloco, 2 if chave == "total" else 1)
            self.kpi[chave] = lbl_v
        return linha_kpi

    def _criar_pagamento(self, layout):

        layout.addWidget(titulo_secao("Pagamento ao fornecedor"))

        grade_formas = QGridLayout()
        grade_formas.setSpacing(8)
        self.botoes_forma = {}
        for indice, (valor, rotulo, icone_nome) in enumerate(_FORMAS_PAGAMENTO):
            bt = QPushButton(rotulo)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setAutoDefault(False)
            bt.setMinimumHeight(40)
            bt.icone_nome = icone_nome
            bt.clicked.connect(lambda _c=False, v=valor: self._escolher_forma(v))
            grade_formas.addWidget(bt, 0, indice)
            self.botoes_forma[valor] = bt
        layout.addLayout(grade_formas)

        estilo_campo = f"""
            QDateEdit, QSpinBox {{
                border:1.5px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:0 10px; font-size:{tokens.TAMANHO_MD}px;
                color:{tokens.TEXTO}; background:{tokens.CARD};
            }}
        """

        self.data_vencimento = QDateEdit()
        self.data_vencimento.setCalendarPopup(True)
        self.data_vencimento.setDisplayFormat("dd/MM/yyyy")
        self.data_vencimento.setDate(QDate.currentDate().addDays(30))
        self.data_vencimento.setMinimumHeight(42)
        self.data_vencimento.setStyleSheet(estilo_campo)

        self.numero_parcelas = QSpinBox()
        self.numero_parcelas.setRange(1, 24)
        self.numero_parcelas.setValue(1)
        self.numero_parcelas.setSuffix("x")
        self.numero_parcelas.setMinimumHeight(42)
        self.numero_parcelas.setStyleSheet(estilo_campo)
        self.numero_parcelas.setToolTip(
            "Uma parcela por mês, no mesmo dia do 1º vencimento "
            "(igual aos boletos do fornecedor)."
        )

        # categoria dos produtos que a nota cria; vazio = sem categoria
        self.categoria = QComboBox()
        self.categoria.setEditable(True)
        self.categoria.setMinimumHeight(42)
        self.categoria.setMinimumWidth(160)
        self.categoria.addItem("")
        self.categoria.lineEdit().setPlaceholderText("Ex.: ROUPA")
        self.categoria.setStyleSheet(estilo_campo.replace("QDateEdit, QSpinBox", "QComboBox"))
        rodar_em_thread(self, listar_categorias, ao_sucesso=self._ao_carregar_categorias)

        self.bloco_vencimento = campo_rotulado("1º vencimento", self.data_vencimento)
        self.bloco_parcelas = campo_rotulado("Parcelas", self.numero_parcelas)

        self.observacao = CampoTexto("Ex.: nota 12345, entregue pelo vendedor João...")

        linha_pag = QHBoxLayout()
        linha_pag.setSpacing(16)
        linha_pag.addWidget(self.bloco_vencimento)
        linha_pag.addWidget(self.bloco_parcelas)
        linha_pag.addWidget(campo_rotulado("Categoria dos produtos novos", self.categoria))
        linha_pag.addWidget(campo_rotulado("Observação (opcional)", self.observacao), 1)
        layout.addLayout(linha_pag)

    def _criar_pagina_revisao(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._criar_cartao_fornecedor())
        layout.addLayout(self._criar_kpis())

        self.chk_atualizar_existentes = QCheckBox(
            "Recalcular também o preço de venda dos produtos já cadastrados pela margem"
        )
        self.chk_atualizar_existentes.setStyleSheet(estilo_checkbox())
        self.chk_atualizar_existentes.toggled.connect(self._recalcular_precos_sugeridos)
        layout.addWidget(self.chk_atualizar_existentes)

        self.tabela = tabela_lista(
            ["Código", "Descrição", "Situação", "Qtd", "Custo", "Preço atual", "Preço venda", "Margem"]
        )
        cab = self.tabela.horizontalHeader()
        for coluna in range(self.tabela.columnCount()):
            cab.setSectionResizeMode(coluna, QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(_COL_DESCRICAO, QHeaderView.Stretch)
        self.tabela.verticalHeader().setDefaultSectionSize(40)
        self.tabela.setMinimumHeight(190)
        # descrição longa numa linha só, com "..." (nome inteiro no tooltip)
        self.tabela.setWordWrap(False)
        self.tabela.setTextElideMode(Qt.ElideRight)
        self.tabela.setSelectionBehavior(self.tabela.SelectionBehavior.SelectItems)
        self.tabela.setEditTriggers(
            self.tabela.EditTrigger.DoubleClicked
            | self.tabela.EditTrigger.EditKeyPressed
            | self.tabela.EditTrigger.AnyKeyPressed
        )
        self.tabela.itemChanged.connect(self._ao_editar_item_tabela)
        layout.addWidget(self.tabela, 1)

        dica = QLabel(
            "Qtd, Custo e Preço venda são editáveis: clique duas vezes ou comece a digitar.  ·  "
            "Margem em vermelho = sem lucro (preço de venda igual ou abaixo do custo)."
        )
        dica.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px; color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(dica)

        self._criar_pagamento(layout)
        self._escolher_forma(self.forma_pagamento)
        return pagina

    # ======================
    # PAGAMENTO
    # ======================

    def _escolher_forma(self, forma):

        self.forma_pagamento = forma
        for valor, bt in self.botoes_forma.items():
            estilo, cor_texto = estilo_botao_forma(
                valor, valor == forma, extra="font-size:13px; padding:0 8px;"
            )
            bt.setStyleSheet(estilo)
            bt.setIcon(icone(bt.icone_nome, cor=cor_texto, tamanho=15))

        self._ao_mudar_forma_pagamento(forma)

    def _ao_carregar_categorias(self, categorias):
        for c in categorias:
            if c.get("ativo", True) and c.get("nome"):
                self.categoria.addItem(c["nome"])

    def _ao_mudar_forma_pagamento(self, forma):
        # boleto tambem gera as parcelas em Contas a Pagar
        a_prazo = forma in ("PRAZO", "BOLETO")
        self.bloco_vencimento.setVisible(a_prazo)
        self.bloco_parcelas.setVisible(a_prazo)

    # ======================
    # SELECAO E PREVIEW
    # ======================

    def selecionar_arquivo(self):

        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar NF-e", "", "XML da NF-e (*.xml)"
        )

        if caminho:
            self.carregar_arquivo(caminho)

    def carregar_arquivo(self, caminho):

        try:
            xml_conteudo = Path(caminho).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            xml_conteudo = Path(caminho).read_text(encoding="latin-1")
        except OSError as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível ler o arquivo.\n{e}")
            return

        self._nome_arquivo = Path(caminho).name
        self.lbl_arquivo.setText(f"Lendo {self._nome_arquivo}...")

        self.bt_selecionar.setEnabled(False)
        self.bt_confirmar.setEnabled(False)

        rodar_em_thread(
            self,
            importar_nfe_preview,
            xml_conteudo,
            ao_sucesso=self._ao_preview_sucesso,
            ao_erro=self._ao_preview_erro,
            ao_finalizar=self._ao_preview_finalizado,
        )

    def _ao_preview_sucesso(self, response):

        if response.status_code != 200:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro ao ler NF-e", str(erro))
            self.lbl_arquivo.setText(_TEXTO_AREA_SOLTAR)
            return

        self.preview = response.json()
        fornecedor = self.preview["fornecedor"]

        self.fornecedor_razao_social.setText(fornecedor.get("razao_social", ""))
        self.fornecedor_margem.blockSignals(True)
        self.fornecedor_margem.setValue(float(fornecedor.get("margem_padrao") or 0))
        self.fornecedor_margem.blockSignals(False)

        texto_cnpj = f"CNPJ {_formatar_cnpj(fornecedor.get('cnpj', ''))}"
        if fornecedor.get("nome_fantasia"):
            texto_cnpj += f"  ·  {fornecedor['nome_fantasia']}"
        self.lbl_fornecedor_cnpj.setText(texto_cnpj)

        encontrado = bool(fornecedor.get("encontrado"))
        self.fornecedor_razao_social.setEnabled(not encontrado)
        self._trocar_badge_fornecedor(encontrado)

        self._preencher_tabela(self.preview["itens"])

        existentes = any(i.get("produto_id") is not None for i in self.preview["itens"])
        self.chk_atualizar_existentes.setChecked(False)
        self.chk_atualizar_existentes.setVisible(existentes)

        self.paginas.setCurrentWidget(self.pagina_revisao)
        self.cabecalho.definir_texto(
            "Importar NF-e", f"{self._nome_arquivo}  ·  confira antes de importar"
        )
        self.bt_confirmar.setEnabled(True)

    def _trocar_badge_fornecedor(self, encontrado):
        # Badge não troca de variante depois de criado: copia o estilo
        # de um novo com a variante certa
        modelo = Badge(
            "Fornecedor já cadastrado" if encontrado else "Fornecedor novo",
            "info" if encontrado else "alerta",
        )
        self.badge_fornecedor.setText(modelo.text())
        self.badge_fornecedor.setStyleSheet(modelo.styleSheet())
        modelo.deleteLater()

    def _ao_preview_erro(self, erro):
        QMessageBox.critical(self, "Erro ao ler NF-e", str(erro))
        self.lbl_arquivo.setText(_TEXTO_AREA_SOLTAR)

    def _ao_preview_finalizado(self):
        self.bt_selecionar.setEnabled(True)

    # ======================
    # TABELA
    # ======================

    def _item(self, texto, editavel=False, direita=False):
        item = QTableWidgetItem(texto)
        if not editavel:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if direita:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return item

    def _preencher_tabela(self, itens):

        self.itens_originais = itens
        self.tabela.blockSignals(True)
        self.tabela.setRowCount(len(itens))

        for linha, item in enumerate(itens):

            novo = item.get("produto_id") is None
            preco_atual = item.get("preco_atual")

            item_status = self._item("● Novo" if novo else "● Cadastrado")
            item_status.setForeground(QColor(tokens.ALERTA if novo else tokens.PRIMARIA))

            # já cadastrado mantém o preço da loja; novo usa a sugestão
            if novo or preco_atual is None:
                preco_venda = float(item["preco_sugerido"])
            else:
                preco_venda = float(preco_atual)

            self.tabela.setItem(linha, _COL_CODIGO, self._item(item["codigo"]))
            item_descricao = self._item(item["descricao"])
            item_descricao.setToolTip(item["descricao"])
            self.tabela.setItem(linha, _COL_DESCRICAO, item_descricao)
            self.tabela.setItem(linha, _COL_STATUS, item_status)
            self.tabela.setItem(linha, _COL_QUANTIDADE, self._item(str(item["quantidade"]), True, True))
            self.tabela.setItem(linha, _COL_CUSTO, self._item(_fmt(float(item["custo"])), True, True))
            self.tabela.setItem(linha, _COL_PRECO_ATUAL, self._item(
                _fmt(float(preco_atual)) if preco_atual is not None else "—", direita=True
            ))
            self.tabela.setItem(linha, _COL_PRECO_VENDA, self._item(_fmt(preco_venda), True, True))
            self.tabela.setItem(linha, _COL_MARGEM, self._item("", direita=True))
            self._atualizar_margem_linha(linha)

        self.tabela.blockSignals(False)
        self._atualizar_totais()

    def _atualizar_margem_linha(self, linha):

        custo = _numero(self.tabela.item(linha, _COL_CUSTO).text())
        venda = _numero(self.tabela.item(linha, _COL_PRECO_VENDA).text())
        item_margem = self.tabela.item(linha, _COL_MARGEM)

        if not custo or venda is None:
            item_margem.setText("—")
            return

        margem = (venda - custo) / custo * 100
        item_margem.setText(f"{margem:.0f}%")
        if venda <= custo:
            cor = tokens.ERRO
        elif margem < 15:
            cor = tokens.ALERTA
        else:
            cor = tokens.SECUNDARIA_HOVER
        item_margem.setForeground(QColor(cor))

        # preço de venda mudado em produto já cadastrado: destaca
        original = self.itens_originais[linha] if linha < len(self.itens_originais) else {}
        item_venda = self.tabela.item(linha, _COL_PRECO_VENDA)
        if self._muda_preco_existente(linha):
            item_venda.setForeground(QColor(tokens.ALERTA_TEXTO))
            item_venda.setToolTip(
                f"Preço de venda vai mudar de R$ {_fmt(float(original['preco_atual']))} "
                f"para R$ {_fmt(venda)}"
            )
        else:
            item_venda.setForeground(QColor(tokens.TEXTO))
            item_venda.setToolTip("")

    def _muda_preco_existente(self, linha):
        """Produto já cadastrado cujo preço de venda na tabela ficou
        diferente do preço atual da loja."""
        original = self.itens_originais[linha]
        if original.get("produto_id") is None or original.get("preco_atual") is None:
            return False
        venda = _numero(self.tabela.item(linha, _COL_PRECO_VENDA).text())
        return venda is not None and round(venda, 2) != round(float(original["preco_atual"]), 2)

    def _atualizar_totais(self):

        total = 0.0
        novos = 0
        for linha, original in enumerate(self.itens_originais):
            qtd = _numero(self.tabela.item(linha, _COL_QUANTIDADE).text()) or 0
            custo = _numero(self.tabela.item(linha, _COL_CUSTO).text()) or 0
            total += qtd * custo
            novos += original.get("produto_id") is None

        self.kpi["itens"].setText(str(len(self.itens_originais)))
        self.kpi["novos"].setText(str(novos))
        self.kpi["existentes"].setText(str(len(self.itens_originais) - novos))
        self.kpi["total"].setText(formatar_moeda(total))
        self.lbl_total_rodape.setText(f"Total da nota: {formatar_moeda(total)}")
        self._total_nota = total

    def _ao_editar_item_tabela(self, item):

        linha, coluna = item.row(), item.column()

        self.tabela.blockSignals(True)
        valor = _numero(item.text())
        if valor is not None:
            # padroniza o que foi digitado ("22.4" vira "22,40")
            item.setText(str(int(valor)) if coluna == _COL_QUANTIDADE else _fmt(valor))
        self.tabela.blockSignals(False)

        # so' recalcula preco sugerido quando o CUSTO muda -- editar o
        # proprio preco de venda manualmente nao deveria ser sobrescrito
        if coluna == _COL_CUSTO:
            self._recalcular_preco_linha(linha)

        self.tabela.blockSignals(True)
        self._atualizar_margem_linha(linha)
        self.tabela.blockSignals(False)
        self._atualizar_totais()

    def _linha_segue_margem(self, linha):
        """Produto novo sempre segue a margem; já cadastrado só se a
        pessoa marcou pra recalcular."""
        original = self.itens_originais[linha]
        return original.get("produto_id") is None or self.chk_atualizar_existentes.isChecked()

    def _recalcular_preco_linha(self, linha):

        if not self._linha_segue_margem(linha):
            return

        custo = _numero(self.tabela.item(linha, _COL_CUSTO).text())
        if custo is None:
            return

        sugerido = custo * (1 + self.fornecedor_margem.value() / 100)

        self.tabela.blockSignals(True)
        self.tabela.item(linha, _COL_PRECO_VENDA).setText(_fmt(sugerido))
        self._atualizar_margem_linha(linha)
        self.tabela.blockSignals(False)

    def _recalcular_precos_sugeridos(self, *_):

        for linha, original in enumerate(self.itens_originais):
            if self._linha_segue_margem(linha):
                self._recalcular_preco_linha(linha)
            elif original.get("preco_atual") is not None:
                # desmarcou "recalcular": volta pro preço atual da loja
                self.tabela.blockSignals(True)
                self.tabela.item(linha, _COL_PRECO_VENDA).setText(_fmt(float(original["preco_atual"])))
                self._atualizar_margem_linha(linha)
                self.tabela.blockSignals(False)

    # ======================
    # CONFIRMACAO
    # ======================

    def confirmar(self):

        if not self.itens_originais:
            return

        razao_social = self.fornecedor_razao_social.text().strip()

        if not razao_social:
            QMessageBox.warning(self, "Atenção", "Informe a razão social do fornecedor.")
            return

        itens_payload = []
        abaixo_do_custo = []
        precos_alterados = 0
        for linha, original in enumerate(self.itens_originais):
            quantidade = _numero(self.tabela.item(linha, _COL_QUANTIDADE).text())
            custo = _numero(self.tabela.item(linha, _COL_CUSTO).text())
            venda = _numero(self.tabela.item(linha, _COL_PRECO_VENDA).text())

            if None in (quantidade, custo, venda) or quantidade <= 0 or venda <= 0:
                QMessageBox.warning(
                    self, "Atenção",
                    f"Confira a linha de \"{original['descricao']}\": quantidade, "
                    "custo e preço de venda precisam ser números maiores que zero."
                )
                self.tabela.setCurrentCell(linha, _COL_QUANTIDADE)
                return

            if venda <= custo:
                abaixo_do_custo.append(original["descricao"])

            muda_preco = self._muda_preco_existente(linha)
            precos_alterados += muda_preco

            itens_payload.append({
                "produto_id": original.get("produto_id"),
                "codigo": original["codigo"],
                "descricao": original["descricao"],
                "codigo_barras": original.get("codigo_barras"),
                "quantidade": int(quantidade),
                "custo": f"{custo:.2f}",
                "preco_venda": f"{venda:.2f}",
                # o backend só troca o preço de venda de produto já
                # cadastrado se pedir -- só pede quando mudou de fato
                "atualizar_preco_venda": muda_preco,
            })

        novos = sum(1 for i in itens_payload if i["produto_id"] is None)
        resumo = (
            f"Importar a nota de {razao_social}?\n\n"
            f"•  {len(itens_payload)} itens, total {formatar_moeda(self._total_nota)}\n"
            f"•  {novos} produto(s) novo(s) serão cadastrados\n"
            f"•  o estoque de todos os itens será somado\n"
            f"•  {precos_alterados} produto(s) já cadastrado(s) terão o preço de venda alterado"
        )
        categoria = self.categoria.currentText().strip()
        if novos:
            resumo += f"\n•  categoria dos novos: {categoria or 'nenhuma'}"
        if self.forma_pagamento in ("PRAZO", "BOLETO"):
            n = self.numero_parcelas.value()
            resumo += (
                f"\n•  {n} parcela(s) em Contas a Pagar, a 1ª em "
                f"{self.data_vencimento.date().toString('dd/MM/yyyy')}"
                + (" e as outras no mesmo dia dos meses seguintes" if n > 1 else "")
            )
        if abaixo_do_custo:
            resumo += (
                f"\n\nATENÇÃO: {len(abaixo_do_custo)} item(ns) vendendo a preço de "
                "custo ou abaixo (sem lucro):\n" + "\n".join(f"   – {d}" for d in abaixo_do_custo[:5])
            )
        if QMessageBox.question(self, "Confirmar importação", resumo) != QMessageBox.Yes:
            return

        fornecedor = self.preview["fornecedor"]

        payload = {
            "forma_pagamento": self.forma_pagamento,
            "itens": itens_payload,
        }

        observacao = self.observacao.text().strip()
        if observacao:
            payload["observacao"] = observacao

        if categoria:
            payload["categoria"] = categoria

        if self.forma_pagamento in ("PRAZO", "BOLETO"):
            payload["data_vencimento"] = self.data_vencimento.date().toString(
                "yyyy-MM-dd"
            )
            payload["numero_parcelas"] = self.numero_parcelas.value()

        if fornecedor.get("encontrado"):
            payload["fornecedor_id"] = fornecedor["id"]
        else:
            payload["fornecedor_novo"] = {
                "razao_social": razao_social,
                "nome_fantasia": fornecedor.get("nome_fantasia"),
                "cnpj": fornecedor["cnpj"],
                "margem_padrao": self.fornecedor_margem.value(),
            }

        self.bt_confirmar.setEnabled(False)
        self.bt_cancelar.setEnabled(False)

        rodar_em_thread(
            self,
            importar_nfe_confirmar,
            payload,
            ao_sucesso=self._ao_confirmar_sucesso,
            ao_erro=self._ao_confirmar_erro,
            ao_finalizar=self._ao_confirmar_finalizado,
        )

    def _ao_confirmar_sucesso(self, response):

        if response.status_code == 200:
            compra = response.json()
            QMessageBox.information(
                self, "Importação concluída",
                f"Compra #{compra['id']} registrada com sucesso -- "
                f"produtos e estoque atualizados."
            )
            self.accept()
        else:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro ao confirmar", str(erro))

    def _ao_confirmar_erro(self, erro):
        QMessageBox.critical(self, "Erro ao confirmar", str(erro))

    def _ao_confirmar_finalizado(self):
        self.bt_confirmar.setEnabled(True)
        self.bt_cancelar.setEnabled(True)
