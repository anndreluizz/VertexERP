from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence, QColor
from PySide6.QtWidgets import QMessageBox, QPushButton, QTableWidgetItem, QDialog

from telas.cadastro_cliente import CadastroClienteWindow
from telas.ficha_cliente import FichaClienteWindow
from services.cliente_service import (
    listar_clientes,
    cadastrar_cliente,
    atualizar_cliente,
    excluir_cliente,
)
from services.fiado_service import buscar_saldos
from services.api import usuario_e_admin
from widgets.base.base_crud_window import BaseCRUDWindow


class Clientes(BaseCRUDWindow):

    titulo = "CLIENTES"

    colunas = [
        "Nome",
        "CPF",
        "Telefone",
        "Endereço",
        "Status",
        "Saldo Devedor",
    ]

    def __init__(self):
        super().__init__()
        # BaseCRUDWindow já chama self.carregar() no final do próprio __init__,
        # então não é preciso chamar de novo aqui.

        # Excluir é uma ação de administrador — operadores não veem o botão.
        if not usuario_e_admin():
            self.toolbar.bt_excluir.setVisible(False)

        # Botão extra: ficha de fiado do cliente (não faz parte do
        # CrudToolbar padrão, só é usado nesta tela).
        self.bt_ficha = QPushButton("📒 Ver Ficha")
        self.bt_ficha.setStyleSheet("""
            QPushButton{
                background:#6A1B9A;
                color:white;
                font-weight:bold;
                border:none;
                border-radius:6px;
                padding:6px 14px;
            }
            QPushButton:hover{
                background:#4A148C;
            }
        """)
        self.toolbar.layout().insertWidget(3, self.bt_ficha)
        self.bt_ficha.clicked.connect(self.ver_ficha)

        # ==========================================
        # ATALHOS DE TECLADO E DUPLO CLIQUE
        # ==========================================
        QShortcut(QKeySequence("Delete"), self, self.excluir)
        QShortcut(QKeySequence("F5"), self, self.carregar)
        QShortcut(QKeySequence("Ctrl+N"), self, self.novo)

        self.tabela.doubleClicked.connect(lambda index: self.ver_ficha())

    # ==========================================
    # CARREGAR CLIENTES
    # ==========================================
    def carregar(self):
        todos = listar_clientes()

        self.clientes = [
            cliente for cliente in todos if cliente.get("ativo", True)
        ]

        self.saldos = buscar_saldos()

        self.preencher_tabela(self.clientes)

    # ==========================================
    # FILTRAR CLIENTES
    # ==========================================
    def filtrar(self):
        texto = self.pesquisa.text().lower().strip()

        if texto == "":
            clientes = self.clientes
        else:
            clientes = [
                cliente
                for cliente in self.clientes
                if texto in cliente["nome"].lower()
                or texto in str(cliente.get("cpf_cnpj") or "").lower()
                or texto in str(cliente.get("telefone") or "").lower()
                or texto in str(cliente.get("endereco") or "").lower()
            ]

        self.preencher_tabela(clientes)

    # ==========================================
    # PREENCHER TABELA
    # ==========================================
    def preencher_tabela(self, clientes):
        self.tabela.setRowCount(len(clientes))

        for linha, cliente in enumerate(clientes):
            self.tabela.setItem(linha, 0, QTableWidgetItem(cliente["nome"]))
            self.tabela.setItem(
                linha, 1, QTableWidgetItem(cliente.get("cpf_cnpj") or "")
            )
            self.tabela.setItem(
                linha, 2, QTableWidgetItem(cliente.get("telefone") or "")
            )
            self.tabela.setItem(
                linha, 3, QTableWidgetItem(cliente.get("endereco") or "")
            )

            status = "Ativo" if cliente.get("ativo", True) else "Inativo"
            self.tabela.setItem(linha, 4, QTableWidgetItem(status))

            saldo = self.saldos.get(str(cliente["id"]), 0.0)
            item_saldo = QTableWidgetItem(
                f"R$ {saldo:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
            )
            item_saldo.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if saldo > 0:
                item_saldo.setForeground(QColor("#C62828"))
            elif saldo < 0:
                item_saldo.setForeground(QColor("#2E7D32"))
            self.tabela.setItem(linha, 5, item_saldo)

    # ==========================================
    # NOVO CLIENTE
    # ==========================================
    def novo(self):
        tela = CadastroClienteWindow()

        if tela.exec() != QDialog.Accepted:
            return

        response = cadastrar_cliente(tela.dados)

        if response.status_code in (200, 201):
            QMessageBox.information(self, "Sucesso", "Cliente cadastrado com sucesso.")
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # EDITAR CLIENTE
    # ==========================================
    def editar(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um cliente.")
            return

        cliente = self.clientes[linha]
        tela = CadastroClienteWindow(cliente)

        if tela.exec() != QDialog.Accepted:
            return

        response = atualizar_cliente(cliente["id"], tela.dados)

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Cliente atualizado.")
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # EXCLUIR CLIENTE
    # ==========================================
    def excluir(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um cliente.")
            return

        cliente = self.clientes[linha]

        resposta = QMessageBox.question(
            self,
            "Excluir",
            f"Deseja realmente excluir \"{cliente['nome']}\"?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_cliente(cliente["id"])

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Cliente excluído.")
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # VER FICHA DO CLIENTE
    # ==========================================
    def ver_ficha(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um cliente.")
            return

        cliente = self.clientes[linha]

        tela = FichaClienteWindow(cliente)
        tela.exec()

    # ==========================================
    # HELPER DE ERRO
    # ==========================================
    def _exibir_erro(self, response):
        try:
            erro = response.json()["detail"]
        except Exception:
            erro = response.text

        QMessageBox.critical(self, "Erro", erro)
