from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem, QDialog

from telas.cadastro_fornecedor import CadastroFornecedorWindow
from services.fornecedor_service import (
    listar_fornecedores,
    cadastrar_fornecedor,
    atualizar_fornecedor,
    excluir_fornecedor,
)
from services.api import usuario_e_admin
from widgets.base.base_crud_window import BaseCRUDWindow


class Fornecedores(BaseCRUDWindow):

    titulo = "FORNECEDORES"

    colunas = [
        "Razão Social",
        "Nome Fantasia",
        "CNPJ",
        "Telefone",
        "Email",
        "Status",
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
    # CARREGAR FORNECEDORES
    # ==========================================
    def carregar(self):
        todos = listar_fornecedores()

        self.fornecedores = [
            fornecedor for fornecedor in todos if fornecedor.get("ativo", True)
        ]

        self.preencher_tabela(self.fornecedores)

    # ==========================================
    # FILTRAR FORNECEDORES
    # ==========================================
    def filtrar(self):
        texto = self.pesquisa.text().lower().strip()

        if texto == "":
            fornecedores = self.fornecedores
        else:
            fornecedores = [
                fornecedor
                for fornecedor in self.fornecedores
                if texto in fornecedor["razao_social"].lower()
                or texto in str(fornecedor.get("nome_fantasia") or "").lower()
                or texto in str(fornecedor.get("cnpj") or "").lower()
                or texto in str(fornecedor.get("telefone") or "").lower()
                or texto in str(fornecedor.get("email") or "").lower()
            ]

        self.preencher_tabela(fornecedores)

    # ==========================================
    # PREENCHER TABELA
    # ==========================================
    def preencher_tabela(self, fornecedores):
        self.tabela.setRowCount(len(fornecedores))

        for linha, fornecedor in enumerate(fornecedores):
            self.tabela.setItem(
                linha, 0, QTableWidgetItem(fornecedor["razao_social"])
            )
            self.tabela.setItem(
                linha, 1, QTableWidgetItem(fornecedor.get("nome_fantasia") or "")
            )
            self.tabela.setItem(
                linha, 2, QTableWidgetItem(fornecedor.get("cnpj") or "")
            )
            self.tabela.setItem(
                linha, 3, QTableWidgetItem(fornecedor.get("telefone") or "")
            )
            self.tabela.setItem(
                linha, 4, QTableWidgetItem(fornecedor.get("email") or "")
            )

            status = "Ativo" if fornecedor.get("ativo", True) else "Inativo"
            self.tabela.setItem(linha, 5, QTableWidgetItem(status))

    # ==========================================
    # NOVO FORNECEDOR
    # ==========================================
    def novo(self):
        tela = CadastroFornecedorWindow()

        if tela.exec() != QDialog.Accepted:
            return

        response = cadastrar_fornecedor(tela.dados)

        if response.status_code in (200, 201):
            QMessageBox.information(
                self, "Sucesso", "Fornecedor cadastrado com sucesso."
            )
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # EDITAR FORNECEDOR
    # ==========================================
    def editar(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um fornecedor.")
            return

        fornecedor = self.fornecedores[linha]
        tela = CadastroFornecedorWindow(fornecedor)

        if tela.exec() != QDialog.Accepted:
            return

        response = atualizar_fornecedor(fornecedor["id"], tela.dados)

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Fornecedor atualizado.")
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # EXCLUIR FORNECEDOR
    # ==========================================
    def excluir(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um fornecedor.")
            return

        fornecedor = self.fornecedores[linha]

        resposta = QMessageBox.question(
            self,
            "Excluir",
            f"Deseja realmente excluir \"{fornecedor['razao_social']}\"?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_fornecedor(fornecedor["id"])

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Fornecedor excluído.")
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # HELPER DE ERRO
    # ==========================================
    def _exibir_erro(self, response):
        try:
            erro = response.json()["detail"]
        except Exception:
            erro = response.text

        QMessageBox.critical(self, "Erro", erro)
