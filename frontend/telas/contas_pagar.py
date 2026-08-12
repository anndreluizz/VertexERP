from datetime import datetime

from PySide6.QtGui import QShortcut, QKeySequence, QColor
from PySide6.QtWidgets import QMessageBox, QPushButton, QTableWidgetItem, QDialog

from telas.cadastro_conta_pagar import CadastroContaPagarWindow
from services.conta_pagar_service import (
    listar_contas_pagar,
    cadastrar_conta_pagar,
    atualizar_conta_pagar,
    pagar_conta_pagar,
    cancelar_conta_pagar,
)
from services.fornecedor_service import listar_fornecedores
from services.api import usuario_e_admin
from widgets.base.base_crud_window import BaseCRUDWindow


class ContasPagar(BaseCRUDWindow):

    titulo = "CONTAS A PAGAR"

    colunas = [
        "Descrição",
        "Nº Boleto",
        "Vencimento",
        "Valor",
        "Status",
    ]

    atalhos_texto = (
        "⌨ F5 Atualizar   •   Ctrl+N Nova Conta   •   "
        "Duplo clique Editar"
    )

    def __init__(self):
        super().__init__()
        # BaseCRUDWindow já chama self.carregar() no final do próprio __init__.

        self.toolbar.bt_editar.setText("✏️ Editar")

        self.bt_pagar = QPushButton("💰 Pagar")
        self.bt_pagar.setStyleSheet("""
            QPushButton{
                background:#2E7D32;
                color:white;
                font-weight:bold;
                border:none;
                border-radius:6px;
                padding:6px 14px;
            }
            QPushButton:hover{
                background:#1B5E20;
            }
        """)
        self.toolbar.layout().insertWidget(2, self.bt_pagar)
        self.bt_pagar.clicked.connect(self.pagar)

        self.toolbar.bt_excluir.setText("🚫 Cancelar")

        # Cancelar é uma ação de administrador — operadores não veem o botão.
        if not usuario_e_admin():
            self.toolbar.bt_excluir.setVisible(False)

        # ==========================================
        # ATALHOS DE TECLADO E DUPLO CLIQUE
        # ==========================================
        QShortcut(QKeySequence("F5"), self, self.carregar)
        QShortcut(QKeySequence("Ctrl+N"), self, self.novo)

        self.tabela.doubleClicked.connect(lambda index: self.editar())

    # ==========================================
    # CARREGAR CONTAS
    # ==========================================
    def carregar(self):
        fornecedores = listar_fornecedores()

        self.fornecedores_map = {
            fornecedor["id"]: fornecedor["razao_social"]
            for fornecedor in fornecedores
        }

        self.contas = listar_contas_pagar()

        self.preencher_tabela(self.contas)

    # ==========================================
    # FILTRAR CONTAS
    # ==========================================
    def filtrar(self):
        texto = self.pesquisa.text().lower().strip()

        if texto == "":
            contas = self.contas
        else:
            contas = [
                conta
                for conta in self.contas
                if texto in self._descricao(conta).lower()
                or texto in str(conta.get("numero_boleto") or "").lower()
            ]

        self.preencher_tabela(contas)

    # ==========================================
    # DESCRIÇÃO (FORNECEDOR OU CONTA AVULSA)
    # ==========================================
    def _descricao(self, conta):
        fornecedor_id = conta.get("fornecedor_id")

        if fornecedor_id and fornecedor_id in self.fornecedores_map:
            return self.fornecedores_map[fornecedor_id]

        return conta.get("observacao") or "Conta avulsa"

    # ==========================================
    # PREENCHER TABELA
    # ==========================================
    def preencher_tabela(self, contas):
        self.tabela.setRowCount(len(contas))

        hoje = datetime.now().date()

        for linha, conta in enumerate(contas):
            self.tabela.setItem(
                linha, 0, QTableWidgetItem(self._descricao(conta))
            )
            self.tabela.setItem(
                linha, 1, QTableWidgetItem(conta.get("numero_boleto") or "")
            )

            vencimento = datetime.fromisoformat(conta["data_vencimento"])
            self.tabela.setItem(
                linha, 2, QTableWidgetItem(vencimento.strftime("%d/%m/%Y"))
            )

            valor_item = QTableWidgetItem(f"R$ {float(conta['valor']):.2f}")
            self.tabela.setItem(linha, 3, valor_item)

            status = conta["status"]

            if status == "PAGO":
                texto_status, cor = "Pago", QColor("#2E7D32")
            elif status == "CANCELADO":
                texto_status, cor = "Cancelado", QColor("#757575")
            elif vencimento.date() < hoje:
                texto_status, cor = "Vencido", QColor("#C62828")
            else:
                texto_status, cor = "Pendente", QColor("#EF6C00")

            item_status = QTableWidgetItem(texto_status)
            item_status.setForeground(cor)
            self.tabela.setItem(linha, 4, item_status)

    # ==========================================
    # NOVA CONTA
    # ==========================================
    def novo(self):
        tela = CadastroContaPagarWindow()

        if tela.exec() != QDialog.Accepted:
            return

        response = cadastrar_conta_pagar(tela.dados)

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Conta cadastrada com sucesso.")
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # EDITAR CONTA
    # ==========================================
    def editar(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione uma conta.")
            return

        conta = self.contas[linha]

        if conta["status"] != "PENDENTE":
            QMessageBox.warning(
                self, "Aviso", "Só é possível editar uma conta pendente."
            )
            return

        conta_com_nome = dict(conta)
        conta_com_nome["fornecedor_nome"] = self._descricao(conta)

        tela = CadastroContaPagarWindow(conta_com_nome)

        if tela.exec() != QDialog.Accepted:
            return

        response = atualizar_conta_pagar(conta["id"], tela.dados)

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Conta atualizada.")
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # PAGAR CONTA
    # ==========================================
    def pagar(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione uma conta.")
            return

        conta = self.contas[linha]

        resposta = QMessageBox.question(
            self,
            "Pagar Conta",
            f"Confirmar o pagamento de R$ {float(conta['valor']):.2f}?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = pagar_conta_pagar(conta["id"])

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Conta paga com sucesso.")
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # CANCELAR CONTA
    # ==========================================
    def excluir(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione uma conta.")
            return

        conta = self.contas[linha]

        resposta = QMessageBox.question(
            self,
            "Cancelar Conta",
            f"Deseja realmente cancelar esta conta de R$ {float(conta['valor']):.2f}?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = cancelar_conta_pagar(conta["id"])

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Conta cancelada.")
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
