from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import BotaoSecundario, CampoTexto
from services.produto_service import atualizar_produto, listar_produtos
from services.worker import rodar_em_thread
from telas.cadastro_produto import CadastroProdutoWindow
from utils.formatacao import formatar_moeda
from widgets.estado_async import PainelErro


# Aba Vitrine: o que esta' no site da loja (ver vitrine/ e app/api/v1/vitrine.py).
# Liga/desliga direto na tabela; o site pega a mudanca na proxima
# publicacao automatica (tarefa agendada, a cada 5 minutos).
FILTROS = [
    ("No site", "SITE"),
    ("Destaques", "DESTAQUE"),
    ("Com pendência", "PENDENCIA"),
    ("Todos os produtos", "TODOS"),
]

COL_PRODUTO, COL_CATEGORIA, COL_PRECO, COL_SITE, COL_DESTAQUE, COL_AVISO = range(6)


def pendencias(produto):
    """O que deixa o produto feio ou escondido no site."""
    faltando = []
    if not produto.get("tem_foto"):
        faltando.append("sem foto")
    if not produto.get("categoria"):
        faltando.append("sem categoria")
    return faltando


def passa_filtro(produto, filtro, termo=""):
    if filtro == "SITE" and not produto.get("vitrine_publicar"):
        return False
    if filtro == "DESTAQUE" and not produto.get("vitrine_destaque"):
        return False
    if filtro == "PENDENCIA" and not (produto.get("vitrine_publicar") and pendencias(produto)):
        return False
    if not termo:
        return True
    campos = " ".join(str(produto.get(k) or "") for k in ("nome", "codigo", "codigo_barras", "categoria"))
    return termo in campos.casefold()


class Vitrine(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.produtos = []
        self.exibidos = []
        self.filtro = "SITE"
        self.botoes = {}
        self._carregando = False

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(12)

        bt_voltar = QPushButton()
        bt_voltar.setFixedSize(36, 36)
        bt_voltar.setCursor(Qt.PointingHandCursor)
        bt_voltar.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        bt_voltar.setToolTip("Voltar")
        bt_voltar.setAccessibleName("Voltar")
        bt_voltar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        bt_voltar.clicked.connect(self.voltar.emit)

        icone_titulo = QLabel()
        icone_titulo.setFixedSize(36, 36)
        icone_titulo.setAlignment(Qt.AlignCenter)
        icone_titulo.setStyleSheet(f"background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_SM}px;")
        icone_titulo.setPixmap(icone_pixmap("globe", cor=tokens.PRIMARIA, tamanho=18))

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)
        titulo = QLabel("Vitrine")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        subtitulo = QLabel(
            "Produtos que aparecem no site da loja. Marque ou desmarque na tabela; "
            "o site atualiza sozinho em até 5 minutos."
        )
        subtitulo.setStyleSheet(f"background:transparent; font-size:{tokens.TAMANHO_XS}px; color:{tokens.TEXTO_TERCIARIO};")
        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        cabecalho.addWidget(bt_voltar)
        cabecalho.addWidget(icone_titulo)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()
        layout.addLayout(cabecalho)

        barra = QHBoxLayout()
        barra.setSpacing(8)
        self.pesquisa = CampoTexto("Buscar por nome, código ou categoria...")
        self.pesquisa.setMinimumWidth(260)
        self.pesquisa.textChanged.connect(self.filtrar)
        barra.addWidget(self.pesquisa, stretch=1)
        barra.addSpacing(8)
        for rotulo, chave in FILTROS:
            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(36)
            bt.clicked.connect(lambda _=False, c=chave: self.selecionar_filtro(c))
            self.botoes[chave] = bt
            barra.addWidget(bt)
        layout.addLayout(barra)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(6)
        self.tabela.setHorizontalHeaderLabels(["Produto", "Categoria", "Preço", "No site", "Destaque", "Aviso"])
        cab = self.tabela.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(COL_PRODUTO, QHeaderView.Stretch)
        cab.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.tabela.verticalHeader().setDefaultSectionSize(44)
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
            QTableWidget::item:selected {{ background: {tokens.PRIMARIA_CLARA}; color: {tokens.TEXTO}; }}
            QHeaderView::section {{
                background: {tokens.CARD}; color: {tokens.TEXTO_SECUNDARIO};
                font-weight: 700; font-size: {tokens.TAMANHO_XS}px;
                padding: 10px 8px; border: none; border-bottom: 1px solid {tokens.BORDA};
            }}
        """)
        self.tabela.itemChanged.connect(self._ao_marcar)
        self.tabela.doubleClicked.connect(
            lambda index: self.editar(index.row()) if index.column() not in (COL_SITE, COL_DESTAQUE) else None
        )
        layout.addWidget(self.tabela, stretch=1)

        self.painel_erro = PainelErro()
        self.painel_erro.tentar_novamente.connect(self.carregar)
        self.painel_erro.hide()
        layout.addWidget(self.painel_erro)

        self.lbl_vazio = QLabel("")
        self.lbl_vazio.setAlignment(Qt.AlignCenter)
        self.lbl_vazio.setWordWrap(True)
        self.lbl_vazio.setStyleSheet(f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_MD}px; padding:32px;")
        self.lbl_vazio.hide()
        layout.addWidget(self.lbl_vazio, stretch=1)

        rodape = QHBoxLayout()
        dicas = QLabel("Duplo clique abre o cadastro do produto (foto, categoria, preço)")
        dicas.setStyleSheet(f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_XS}px;")
        self.lbl_resumo = QLabel("")
        self.lbl_resumo.setStyleSheet(f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_SM}px;")
        self.bt_atualizar = BotaoSecundario("Atualizar", icone_nome="refresh-cw")
        self.bt_atualizar.clicked.connect(self.carregar)
        rodape.addWidget(dicas)
        rodape.addStretch()
        rodape.addWidget(self.lbl_resumo)
        rodape.addSpacing(12)
        rodape.addWidget(self.bt_atualizar)
        layout.addLayout(rodape)

        self._marcar_filtro(self.filtro)

    # ======================
    # CARREGAMENTO
    # ======================

    def carregar(self):
        if self._carregando:
            return
        self._carregando = True
        self.bt_atualizar.setEnabled(False)
        self.lbl_resumo.setText("Carregando...")
        rodar_em_thread(
            self,
            listar_produtos,
            ao_sucesso=self._ao_carregar,
            ao_erro=self._ao_erro_carregar,
            ao_finalizar=self._ao_finalizar_carga,
        )

    def _ao_carregar(self, produtos):
        # o site so' mostra produto ativo
        self.produtos = sorted((p for p in produtos if p.get("ativo", True)), key=lambda p: p["nome"].casefold())
        self.painel_erro.hide()
        self.filtrar()

    def _ao_erro_carregar(self, erro):
        self.tabela.setRowCount(0)
        self.tabela.hide()
        self.lbl_vazio.hide()
        self.painel_erro.definir_mensagem(f"Não foi possível carregar os produtos.\n{erro}")
        self.painel_erro.show()
        self.lbl_resumo.setText("Falha ao carregar")

    def _ao_finalizar_carga(self):
        self._carregando = False
        self.bt_atualizar.setEnabled(True)

    # ======================
    # FILTROS
    # ======================

    def selecionar_filtro(self, chave):
        self._marcar_filtro(chave)
        self.filtrar()

    def _marcar_filtro(self, chave):
        self.filtro = chave
        for k, botao in self.botoes.items():
            sel = k == chave
            botao.setChecked(sel)
            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.PRIMARIA_CLARA if sel else tokens.CARD};
                    color: {tokens.PRIMARIA if sel else tokens.TEXTO_SECUNDARIO};
                    border-radius: {tokens.RADIUS_SM}px;
                    border: 1px solid {tokens.PRIMARIA_CLARA if sel else tokens.BORDA};
                    font-weight: {700 if sel else 600};
                    font-size: {tokens.TAMANHO_SM}px;
                    padding: 0 14px;
                }}
                QPushButton:hover {{ background: {tokens.PRIMARIA_CLARA if sel else tokens.FUNDO}; }}
            """)

    def filtrar(self):
        termo = self.pesquisa.text().strip().casefold()
        for rotulo, chave in FILTROS:
            self.botoes[chave].setText(f"{rotulo}  {sum(passa_filtro(p, chave) for p in self.produtos)}")

        self.exibidos = [p for p in self.produtos if passa_filtro(p, self.filtro, termo)]
        self.preencher_tabela()

        no_site = sum(1 for p in self.produtos if p.get("vitrine_publicar"))
        self.lbl_resumo.setText(f"{no_site} produto{'s' if no_site != 1 else ''} no site")

        if self.exibidos or self.painel_erro.isVisible():
            self.lbl_vazio.hide()
            self.tabela.setVisible(not self.painel_erro.isVisible())
            return
        self.tabela.hide()
        self.lbl_vazio.setText(
            "Nenhum produto no site ainda.\nAbra \"Todos os produtos\" e marque \"No site\" nos que quiser mostrar."
            if self.filtro == "SITE" and not termo
            else "Nenhum produto encontrado."
        )
        self.lbl_vazio.show()

    def preencher_tabela(self):
        self.tabela.blockSignals(True)
        self.tabela.setRowCount(len(self.exibidos))
        for linha, p in enumerate(self.exibidos):
            self.tabela.setItem(linha, COL_PRODUTO, QTableWidgetItem(f"{p['nome']}   ({p['codigo']})"))
            self.tabela.setItem(linha, COL_CATEGORIA, QTableWidgetItem(p.get("categoria") or ""))
            preco = QTableWidgetItem(formatar_moeda(p.get("preco_efetivo", p.get("preco_venda"))))
            preco.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tabela.setItem(linha, COL_PRECO, preco)

            for coluna, campo in ((COL_SITE, "vitrine_publicar"), (COL_DESTAQUE, "vitrine_destaque")):
                item = QTableWidgetItem()
                flags = Qt.ItemIsUserCheckable | Qt.ItemIsSelectable
                # destaque so' vale pra quem esta' no site (igual ao cadastro)
                if coluna == COL_SITE or p.get("vitrine_publicar"):
                    flags |= Qt.ItemIsEnabled
                item.setFlags(flags)
                item.setCheckState(Qt.Checked if p.get(campo) else Qt.Unchecked)
                self.tabela.setItem(linha, coluna, item)

            faltando = pendencias(p) if p.get("vitrine_publicar") else []
            aviso = QTableWidgetItem(", ".join(faltando).capitalize())
            if faltando:
                aviso.setForeground(QColor(tokens.ALERTA_TEXTO))
                aviso.setIcon(icone("alert-triangle", cor=tokens.ALERTA_TEXTO, tamanho=14))
            self.tabela.setItem(linha, COL_AVISO, aviso)
        self.tabela.blockSignals(False)

    # ======================
    # LIGAR / DESLIGAR NO SITE
    # ======================

    def _ao_marcar(self, item):
        coluna = item.column()
        if coluna not in (COL_SITE, COL_DESTAQUE):
            return
        p = self.exibidos[item.row()]
        marcado = item.checkState() == Qt.Checked
        publicar = marcado if coluna == COL_SITE else p.get("vitrine_publicar", False)
        destaque = (marcado if coluna == COL_DESTAQUE else p.get("vitrine_destaque", False)) and publicar
        # parcial: codigo/nome sao exigidos pelo schema, o resto fica como
        # esta' (exclude_unset no backend, igual ao favorito do F1)
        dados = {"codigo": p["codigo"], "nome": p["nome"], "vitrine_publicar": publicar, "vitrine_destaque": destaque}
        rodar_em_thread(
            self,
            atualizar_produto,
            p["id"],
            dados,
            ao_sucesso=lambda r, p=p, d=dados: self._ao_salvar(r, p, d),
            ao_erro=lambda erro: self._ao_falhar(str(erro)),
        )

    def _ao_salvar(self, response, produto, dados):
        if response.status_code != 200:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            self._ao_falhar(erro)
            return
        produto["vitrine_publicar"] = dados["vitrine_publicar"]
        produto["vitrine_destaque"] = dados["vitrine_destaque"]
        self.filtrar()

    def _ao_falhar(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível alterar a vitrine.\n{erro}")
        self.filtrar()  # volta a marcacao pro que esta' salvo

    # ======================
    # EDITAR (foto, categoria, preco)
    # ======================

    def editar(self, linha):
        if not 0 <= linha < len(self.exibidos):
            return
        tela = CadastroProdutoWindow(self.exibidos[linha])
        if tela.exec() != QDialog.Accepted:
            return
        rodar_em_thread(
            self,
            atualizar_produto,
            self.exibidos[linha]["id"],
            tela.dados,
            ao_sucesso=self._ao_editar,
            ao_erro=lambda erro: QMessageBox.critical(self, "Erro", str(erro)),
        )

    def _ao_editar(self, response):
        if response.status_code != 200:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", erro)
        self.carregar()
