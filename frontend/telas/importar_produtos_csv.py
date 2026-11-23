"""Importação em massa de produtos via planilha CSV -- pro lojista com
muita variedade de mercadoria e sem nota fiscal (XML) pra usar o
import de NF-e já existente em Fornecedores/Compras, cadastrar um por
um em "Novo Produto" era o único jeito até aqui."""
import csv

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.widgets import Badge, BotaoPrimario, BotaoSecundario, Card, DialogoPadrao
from services.produto_service import importar_csv_confirmar, importar_csv_preview
from services.worker import rodar_em_thread
from utils.formatacao import formatar_moeda
from widgets.dialogs.message_dialog import Mensagem

MODELO_CABECALHO = [
    "Código", "Nome", "Categoria", "Código de Barras",
    "Preço de Custo", "Preço de Venda", "Estoque", "Estoque Mínimo",
    "Unidade",
]

MODELO_EXEMPLO = [
    "", "Camiseta Branca P", "Roupa", "",
    "15,00", "39,90", "10", "2", "UN",
]


def ler_texto_csv(dados):
    """O Excel em portugues salva "CSV (separado por virgulas)" em
    ANSI (cp1252), nao UTF-8 -- sem o fallback "CALÇADOS" quebrava a
    leitura."""
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dados.decode("cp1252")


class ImportarProdutosCsvDialog(DialogoPadrao):

    importado = Signal()

    def __init__(self, parent=None):

        super().__init__(
            "Importar produtos",
            "Cadastre vários de uma vez com uma planilha CSV",
            "file-text",
            largura=DialogoPadrao.GRANDE,
            parent=parent,
        )

        self._itens_preview = []
        self.resize(DialogoPadrao.GRANDE, 620)

        self.paginas = QStackedWidget()
        self.pagina_selecao = self._criar_pagina_selecao()
        self.pagina_preview = self._criar_pagina_preview()
        self.paginas.addWidget(self.pagina_selecao)
        self.paginas.addWidget(self.pagina_preview)
        self.corpo.addWidget(self.paginas, stretch=1)

        # rodapé único: na seleção "Selecionar arquivo", na conferência
        # "Escolher outro arquivo" (à esquerda) e "Confirmar importação"
        self.bt_escolher = BotaoPrimario("Selecionar arquivo CSV…", icone_nome="file-text")
        self.bt_escolher.clicked.connect(self._escolher_arquivo)
        self.definir_botoes(self.bt_escolher)

        self.bt_confirmar = BotaoPrimario("Confirmar importação", icone_nome="check")
        self.bt_confirmar.setMinimumWidth(220)
        self.bt_confirmar.clicked.connect(self._confirmar)
        self.rodape.addWidget(self.bt_confirmar)

        self.bt_voltar = BotaoSecundario("Escolher outro arquivo")
        self.bt_voltar.clicked.connect(lambda: self._mostrar_pagina(self.pagina_selecao))
        self.rodape.insertWidget(0, self.bt_voltar)

        self._mostrar_pagina(self.pagina_selecao)

    def _mostrar_pagina(self, pagina):
        selecao = pagina is self.pagina_selecao
        self.paginas.setCurrentWidget(pagina)
        self.bt_escolher.setVisible(selecao)
        self.bt_confirmar.setVisible(not selecao)
        self.bt_voltar.setVisible(not selecao)

    # ==========================================
    # PÁGINA 1: SELEÇÃO DO ARQUIVO
    # ==========================================

    @staticmethod
    def _passo(numero, titulo, texto, botao=None):
        """Linha de passo: a ordem importa (baixar, preencher, selecionar)."""

        cartao = Card(sombra=False)
        linha = QHBoxLayout(cartao)
        linha.setContentsMargins(18, 16, 18, 16)
        linha.setSpacing(14)

        bolinha = QLabel(str(numero))
        bolinha.setFixedSize(34, 34)
        bolinha.setAlignment(Qt.AlignCenter)
        bolinha.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA};
            border-radius:17px; font-weight:800; font-size:{tokens.TAMANHO_BASE}px;
        """)

        col = QVBoxLayout()
        col.setSpacing(2)
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:800;
        """)
        lbl_texto = QLabel(texto)
        lbl_texto.setWordWrap(True)
        lbl_texto.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        col.addWidget(lbl_titulo)
        col.addWidget(lbl_texto)

        linha.addWidget(bolinha, 0, Qt.AlignTop)
        linha.addLayout(col, 1)
        if botao is not None:
            linha.addWidget(botao, 0, Qt.AlignVCenter)
        return cartao

    def _criar_pagina_selecao(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        bt_modelo = BotaoSecundario("Baixar modelo CSV", icone_nome="download")
        bt_modelo.clicked.connect(self._baixar_modelo)

        layout.addWidget(self._passo(
            1, "Baixe o modelo",
            "Planilha com as colunas certas e uma linha de exemplo.", bt_modelo,
        ))
        layout.addWidget(self._passo(
            2, "Preencha uma linha por produto",
            "Pode usar Excel, Google Planilhas ou LibreOffice. Salve como CSV.",
        ))
        layout.addWidget(self._passo(
            3, "Selecione o arquivo preenchido",
            "Você confere tudo na próxima tela antes de importar.",
        ))

        aviso = QLabel(
            "Produto com o mesmo código (ou código de barras) de um já "
            "cadastrado é atualizado, não duplicado."
        )
        aviso.setWordWrap(True)
        aviso.setStyleSheet(f"""
            background:{tokens.ALERTA_CLARO}; color:{tokens.ALERTA_TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
            border-radius:{tokens.RADIUS_SM}px; padding:12px 14px;
        """)
        layout.addWidget(aviso)
        layout.addStretch()

        return pagina

    def _baixar_modelo(self):

        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar Modelo CSV", "modelo_produtos.csv", "Arquivo CSV (*.csv)"
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".csv"):
            caminho += ".csv"

        try:
            with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:
                escritor = csv.writer(arquivo, delimiter=";")
                escritor.writerow(MODELO_CABECALHO)
                escritor.writerow(MODELO_EXEMPLO)
        except OSError as erro:
            Mensagem.erro(self, f"Não foi possível salvar o modelo.\n{erro}")
            return

        Mensagem.sucesso(
            self,
            "Modelo salvo. Preencha uma linha por produto e volte "
            "aqui pra selecionar o arquivo preenchido.",
        )

    def _escolher_arquivo(self):

        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Planilha CSV", "", "Arquivo CSV (*.csv)"
        )

        if not caminho:
            return

        try:
            with open(caminho, "rb") as arquivo:
                conteudo = ler_texto_csv(arquivo.read())
        except OSError as erro:
            Mensagem.erro(self, f"Não foi possível ler o arquivo.\n{erro}")
            return

        if not conteudo.strip():
            Mensagem.aviso(self, "O arquivo selecionado está vazio.")
            return

        self.bt_escolher.setEnabled(False)

        rodar_em_thread(
            self,
            importar_csv_preview,
            conteudo,
            ao_sucesso=self._ao_preview_sucesso,
            ao_erro=self._ao_preview_erro,
            ao_finalizar=self._ao_preview_finalizado,
        )

    def _ao_preview_finalizado(self):
        self.bt_escolher.setEnabled(True)

    def _ao_preview_erro(self, erro):
        Mensagem.erro(self, f"Não foi possível ler a planilha.\n{erro}")

    def _ao_preview_sucesso(self, dados):

        self._itens_preview = dados["itens"]

        if not self._itens_preview:
            Mensagem.aviso(
                self,
                "Nenhuma linha de produto encontrada na planilha "
                "(confira se o cabeçalho está na primeira linha).",
            )
            return

        self._popular_preview(dados)
        self._mostrar_pagina(self.pagina_preview)

    # ==========================================
    # PÁGINA 2: CONFERÊNCIA E CONFIRMAÇÃO
    # ==========================================

    def _criar_pagina_preview(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # contagens em selos: dá pra bater o olho no que vai acontecer
        self.linha_resumo = QHBoxLayout()
        self.linha_resumo.setSpacing(8)
        self.linha_resumo.addStretch()
        layout.addLayout(self.linha_resumo)

        self.tabela_preview = QTableWidget()
        self.tabela_preview.setMinimumHeight(320)
        self.tabela_preview.setColumnCount(4)
        self.tabela_preview.setHorizontalHeaderLabels(
            ["Linha", "Produto", "Preço de Venda", "Situação"]
        )
        self.tabela_preview.verticalHeader().setVisible(False)
        self.tabela_preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela_preview.setSelectionMode(QTableWidget.NoSelection)
        cab = self.tabela_preview.horizontalHeader()
        cab.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(1, QHeaderView.Stretch)
        cab.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        cab.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.tabela_preview.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                font-size: {tokens.TAMANHO_SM}px;
            }}
            QHeaderView::section {{
                background: {tokens.FUNDO};
                color: {tokens.TEXTO_SECUNDARIO};
                font-weight: 700;
                padding: 8px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
        """)
        layout.addWidget(self.tabela_preview, stretch=1)

        return pagina

    def _popular_preview(self, dados):

        while self.linha_resumo.count() > 1:
            item = self.linha_resumo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for posicao, (texto, variante) in enumerate((
            (f"{dados['total_novos']} novo(s)", "sucesso"),
            (f"{dados['total_atualizados']} será(ão) atualizado(s)", "alerta"),
            (
                f"{dados['total_com_erro']} com erro, não serão importados",
                "erro" if dados["total_com_erro"] else "neutro",
            ),
        )):
            self.linha_resumo.insertWidget(posicao, Badge(texto, variante))

        itens = dados["itens"]
        self.tabela_preview.setRowCount(len(itens))

        for linha, item in enumerate(itens):

            self.tabela_preview.setItem(
                linha, 0, QTableWidgetItem(str(item["linha"]))
            )
            self.tabela_preview.setItem(
                linha, 1, QTableWidgetItem(item["nome"] or "—")
            )
            self.tabela_preview.setItem(
                linha, 2, QTableWidgetItem(formatar_moeda(item["preco_venda"]))
            )

            if item["erro"]:
                texto_situacao = f"Erro: {item['erro']}"
                cor_situacao = tokens.ERRO
            elif item["produto_id"]:
                texto_situacao = "Atualiza existente"
                cor_situacao = tokens.ALERTA_TEXTO
            else:
                texto_situacao = "Novo produto"
                cor_situacao = tokens.SECUNDARIA_HOVER

            item_situacao = QTableWidgetItem(texto_situacao)
            item_situacao.setForeground(QColor(cor_situacao))
            self.tabela_preview.setItem(linha, 3, item_situacao)

        validos = sum(1 for item in itens if not item["erro"])
        self.bt_confirmar.setEnabled(validos > 0)
        self.bt_confirmar.setText(f"Confirmar importação ({validos})")

    def _confirmar(self):

        itens_validos = [
            item for item in self._itens_preview if not item["erro"]
        ]

        if not itens_validos:
            return

        self.bt_confirmar.setEnabled(False)

        rodar_em_thread(
            self,
            importar_csv_confirmar,
            itens_validos,
            ao_sucesso=self._ao_confirmar_sucesso,
            ao_erro=self._ao_confirmar_erro,
            ao_finalizar=self._ao_confirmar_finalizado,
        )

    def _ao_confirmar_finalizado(self):
        self.bt_confirmar.setEnabled(True)

    def _ao_confirmar_erro(self, erro):
        Mensagem.erro(self, f"Não foi possível importar os produtos.\n{erro}")

    def _ao_confirmar_sucesso(self, resultado):

        Mensagem.sucesso(
            self,
            f"{resultado['criados']} produto(s) criado(s) e "
            f"{resultado['atualizados']} atualizado(s) com sucesso.",
        )

        self.importado.emit()
        self.accept()
