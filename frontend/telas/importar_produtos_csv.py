"""Importação em massa de produtos via planilha CSV -- pro lojista com
muita variedade de mercadoria e sem nota fiscal (XML) pra usar o
import de NF-e já existente em Fornecedores/Compras, cadastrar um por
um em "Novo Produto" era o único jeito até aqui."""
import csv
import io

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.widgets import BotaoPrimario, BotaoSecundario
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


class ImportarProdutosCsvDialog(QDialog):

    importado = Signal()

    def __init__(self, parent=None):

        super().__init__(parent)

        self._itens_preview = []

        self.setWindowTitle("Importar Produtos (CSV)")
        self.resize(700, 520)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Importar Produtos")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)
        layout.addWidget(titulo)

        self.paginas = QStackedWidget()
        self.pagina_selecao = self._criar_pagina_selecao()
        self.pagina_preview = self._criar_pagina_preview()
        self.paginas.addWidget(self.pagina_selecao)
        self.paginas.addWidget(self.pagina_preview)
        layout.addWidget(self.paginas, stretch=1)

    # ==========================================
    # PÁGINA 1: SELEÇÃO DO ARQUIVO
    # ==========================================

    def _criar_pagina_selecao(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setSpacing(14)

        instrucoes = QLabel(
            "Cadastre vários produtos de uma vez com uma planilha CSV "
            "(Excel, Google Planilhas ou LibreOffice, salvando como "
            "\"CSV\").\n\n"
            "Não tem uma planilha ainda? Baixe o modelo abaixo, "
            "preencha (uma linha por produto) e volte aqui pra "
            "selecionar o arquivo preenchido.\n\n"
            "Produtos com o mesmo código (ou código de barras) de um "
            "já cadastrado são atualizados, não duplicados."
        )
        instrucoes.setWordWrap(True)
        instrucoes.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(instrucoes)

        layout.addStretch()

        bt_modelo = BotaoSecundario("Baixar Modelo CSV", icone_nome="download")
        bt_modelo.clicked.connect(self._baixar_modelo)
        layout.addWidget(bt_modelo)

        self.bt_escolher = BotaoPrimario(
            "Selecionar Arquivo CSV...", icone_nome="file-text"
        )
        self.bt_escolher.clicked.connect(self._escolher_arquivo)
        layout.addWidget(self.bt_escolher)

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
            with open(caminho, encoding="utf-8-sig") as arquivo:
                conteudo = arquivo.read()
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
        self.paginas.setCurrentWidget(self.pagina_preview)

    # ==========================================
    # PÁGINA 2: CONFERÊNCIA E CONFIRMAÇÃO
    # ==========================================

    def _criar_pagina_preview(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setSpacing(10)

        self.lbl_resumo = QLabel()
        self.lbl_resumo.setWordWrap(True)
        self.lbl_resumo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(self.lbl_resumo)

        self.tabela_preview = QTableWidget()
        self.tabela_preview.setColumnCount(4)
        self.tabela_preview.setHorizontalHeaderLabels(
            ["Linha", "Produto", "Preço de Venda", "Situação"]
        )
        self.tabela_preview.verticalHeader().setVisible(False)
        self.tabela_preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela_preview.setSelectionMode(QTableWidget.NoSelection)
        self.tabela_preview.horizontalHeader().setStretchLastSection(True)
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

        botoes = QHBoxLayout()

        bt_voltar = BotaoSecundario("Escolher Outro Arquivo")
        bt_voltar.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.pagina_selecao)
        )
        botoes.addWidget(bt_voltar)
        botoes.addStretch()

        self.bt_confirmar = BotaoPrimario("Confirmar Importação")
        self.bt_confirmar.clicked.connect(self._confirmar)
        botoes.addWidget(self.bt_confirmar)

        layout.addLayout(botoes)

        return pagina

    def _popular_preview(self, dados):

        self.lbl_resumo.setText(
            f"{dados['total_novos']} produto(s) novo(s) · "
            f"{dados['total_atualizados']} serão atualizados · "
            f"{dados['total_com_erro']} com erro (não serão importados)"
        )

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
        self.bt_confirmar.setText(f"Confirmar Importação ({validos})")

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
