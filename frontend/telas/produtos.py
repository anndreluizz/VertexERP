from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem, QDialog

from telas.cadastro_produto import CadastroProdutoWindow
from services.produto_service import (
    listar_produtos,
    cadastrar_produto,
    atualizar_produto,
    excluir_produto,
)
from services.api import usuario_e_admin
from widgets.base.base_crud_window import BaseCRUDWindow


class Produtos(BaseCRUDWindow):

    titulo = "PRODUTOS"

    colunas = [
        "Código",
        "Nome",
        "Preço",
        "Estoque",
        "Status",
    ]

    campos = [
        "codigo",
        "nome",
        "preco_venda",
        "estoque",
        "ativo",
    ]

    def __init__(self):
        super().__init__()
        # BaseCRUDWindow já chama self.carregar() no final do próprio __init__,
        # então não é preciso chamar de novo aqui.

        # Excluir é uma ação de administrador — operadores não veem o botão.
        if not usuario_e_admin():
            self.toolbar.bt_excluir.setVisible(False)

        # ==========================================
        # ATALHOS DE TECLADO E DUPLO CLIQUE
        # ==========================================
        QShortcut(QKeySequence("Delete"), self, self.excluir)
        QShortcut(QKeySequence("F5"), self, self.carregar)
        QShortcut(QKeySequence("Ctrl+N"), self, self.novo)

        self.tabela.doubleClicked.connect(lambda index: self.editar())

    # ==========================================
    # CARREGAR PRODUTOS
    # ==========================================
    def carregar(self):
        self.produtos = listar_produtos()
        self.preencher_tabela(self.produtos)

    # ==========================================
    # FILTRAR PRODUTOS
    # ==========================================
    def filtrar(self):
        texto = self.pesquisa.text().lower().strip()

        if texto == "":
            produtos = self.produtos
        else:
            produtos = [
                produto
                for produto in self.produtos
                if texto in str(produto.get("codigo", "")).lower()
                or texto in str(produto.get("codigo_barras") or "").lower()
                or texto in str(produto.get("nome", "")).lower()
                or texto in str(produto.get("categoria") or "").lower()
            ]

        self.preencher_tabela(produtos)

    # ==========================================
    # PREENCHER TABELA
    # ==========================================
    def preencher_tabela(self, produtos):
        self.tabela.setRowCount(len(produtos))

        for linha, produto in enumerate(produtos):
            self.tabela.setItem(linha, 0, QTableWidgetItem(str(produto["codigo"])))
            self.tabela.setItem(linha, 1, QTableWidgetItem(produto["nome"]))
            self.tabela.setItem(
                linha, 2, QTableWidgetItem(f'R$ {float(produto["preco_venda"]):.2f}')
            )
            self.tabela.setItem(linha, 3, QTableWidgetItem(str(produto["estoque"])))

            status = "Ativo" if produto.get("ativo", True) else "Inativo"
            self.tabela.setItem(linha, 4, QTableWidgetItem(status))

    # ==========================================
    # NOVO PRODUTO
    # ==========================================
    def novo(self):
        tela = CadastroProdutoWindow(codigo_sugerido=self._proximo_codigo())

        if tela.exec() != QDialog.Accepted:
            return

        response = cadastrar_produto(tela.dados)

        if response.status_code == 201:
            QMessageBox.information(self, "Sucesso", "Produto cadastrado com sucesso.")
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # EDITAR PRODUTO
    # ==========================================
    def editar(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um produto.")
            return

        produto = self.produtos[linha]
        tela = CadastroProdutoWindow(produto)

        if tela.exec() != QDialog.Accepted:
            return

        response = atualizar_produto(produto["id"], tela.dados)

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Produto atualizado com sucesso.")
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # EXCLUIR PRODUTO
    # ==========================================
    def excluir(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um produto.")
            return

        produto = self.produtos[linha]

        resposta = QMessageBox.question(
            self,
            "Excluir Produto",
            f"Deseja excluir o produto\n\n{produto['nome']} ?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_produto(produto["id"])

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Produto excluído.")
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # PRÓXIMO CÓDIGO SEQUENCIAL
    # ==========================================
    def _proximo_codigo(self):
        maior = 0

        for produto in self.produtos:
            codigo = str(produto.get("codigo") or "")

            if codigo.isdigit():
                maior = max(maior, int(codigo))

        return f"{maior + 1:06d}"

    # ==========================================
    # HELPER DE ERRO (evita repetir o try/except 3x)
    # ==========================================
    def _exibir_erro(self, response):
        try:
            erro = response.json()["detail"]
        except Exception:
            erro = response.text

        QMessageBox.critical(self, "Erro", erro)