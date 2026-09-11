from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
)

from services.venda_service import listar_vendas_pagina, cancelar_venda
from services.cliente_service import listar_clientes
from services.api import usuario_e_admin
from utils.formatacao import formatar_moeda
from widgets.base.base_crud_window import BaseCRUDWindow

_TAMANHO_PAGINA = 100

FORMAS_PAGAMENTO = {
    "DINHEIRO": "Dinheiro",
    "PIX": "PIX",
    "DEBITO": "Débito",
    "CREDITO": "Crédito",
    "BOLETO": "Boleto",
    "PRAZO": "Crediário",
}


class Vendas(BaseCRUDWindow):

    titulo = "VENDAS"

    colunas = [
        "ID",
        "Data",
        "Cliente",
        "Pagamento",
        "Total",
        "Status",
    ]

    atalhos_texto = (
        "⌨ F5 Atualizar   •   Delete Cancelar Venda   •   "
        "Duplo clique Ver Itens"
    )

    def __init__(self):

        self.vendas = []
        self.tem_mais_vendas = False

        super().__init__()

        # Vendas só são criadas pelo PDV, não por aqui.
        self.toolbar.bt_novo.setVisible(False)

        self.toolbar.bt_editar.setText("👁 Ver Itens")
        self.toolbar.bt_excluir.setText("🚫 Cancelar Venda")

        # Cancelar venda é uma ação de administrador — operadores não veem o botão.
        if not usuario_e_admin():
            self.toolbar.bt_excluir.setVisible(False)

        self.bt_carregar_mais = QPushButton("Carregar mais vendas ▾")
        self.bt_carregar_mais.setCursor(Qt.PointingHandCursor)
        self.bt_carregar_mais.clicked.connect(self.carregar_mais)
        self.layout().addWidget(self.bt_carregar_mais)
        self.bt_carregar_mais.setVisible(self.tem_mais_vendas)

        QShortcut(QKeySequence("F5"), self, self.carregar)
        QShortcut(QKeySequence("Delete"), self, self.excluir)

        self.tabela.doubleClicked.connect(lambda index: self.editar())

    # ==========================================
    # CARREGAR VENDAS (paginado — mais recentes primeiro)
    # ==========================================
    def carregar(self):
        self.clientes_map = {
            cliente["id"]: cliente["nome"] for cliente in listar_clientes()
        }

        self.vendas = []
        self._buscar_pagina()

    def carregar_mais(self):
        self._buscar_pagina()

    def _buscar_pagina(self):
        pagina = listar_vendas_pagina(len(self.vendas), _TAMANHO_PAGINA)

        self.vendas.extend(pagina)
        self.tem_mais_vendas = len(pagina) == _TAMANHO_PAGINA

        botao = getattr(self, "bt_carregar_mais", None)
        if botao is not None:
            botao.setVisible(self.tem_mais_vendas)

        self.preencher_tabela(self.vendas)

    # ==========================================
    # FILTRAR VENDAS
    # ==========================================
    def filtrar(self):
        texto = self.pesquisa.text().lower().strip()

        if texto == "":
            vendas = self.vendas
        else:
            vendas = [
                venda
                for venda in self.vendas
                if texto in str(venda["id"])
                or texto in self._nome_cliente(venda).lower()
                or texto in venda["status"].lower()
                or texto in venda["forma_pagamento"].lower()
            ]

        self.preencher_tabela(vendas)

    # ==========================================
    # PREENCHER TABELA
    # ==========================================
    def preencher_tabela(self, vendas):
        self.tabela.setRowCount(len(vendas))

        for linha, venda in enumerate(vendas):
            data = datetime.fromisoformat(venda["data"]).strftime("%d/%m/%Y %H:%M")

            self.tabela.setItem(linha, 0, QTableWidgetItem(str(venda["id"])))
            self.tabela.setItem(linha, 1, QTableWidgetItem(data))
            self.tabela.setItem(linha, 2, QTableWidgetItem(self._nome_cliente(venda)))
            self.tabela.setItem(
                linha,
                3,
                QTableWidgetItem(
                    FORMAS_PAGAMENTO.get(
                        venda["forma_pagamento"], venda["forma_pagamento"]
                    )
                ),
            )
            self.tabela.setItem(
                linha, 4, QTableWidgetItem(formatar_moeda(venda["valor_total"]))
            )
            self.tabela.setItem(linha, 5, QTableWidgetItem(venda["status"]))

    def _nome_cliente(self, venda):
        return self.clientes_map.get(venda["cliente_id"], "Consumidor Final")

    # ==========================================
    # VER ITENS DA VENDA
    # ==========================================
    def editar(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione uma venda.")
            return

        venda = self.vendas[linha]

        linhas = [
            f"- {item['quantidade']}x produto #{item['produto_id']} "
            f"= {formatar_moeda(item['subtotal'])}"
            for item in venda["itens"]
        ]

        QMessageBox.information(
            self,
            f"Itens da Venda #{venda['id']}",
            "\n".join(linhas) or "Nenhum item.",
        )

    # ==========================================
    # CANCELAR VENDA
    # ==========================================
    def excluir(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione uma venda.")
            return

        venda = self.vendas[linha]

        if venda["status"] == "CANCELADA":
            QMessageBox.warning(self, "Aviso", "Essa venda já está cancelada.")
            return

        resposta = QMessageBox.question(
            self,
            "Cancelar Venda",
            f"Deseja cancelar a venda #{venda['id']}?\n"
            "O estoque dos produtos será restaurado.",
        )

        if resposta != QMessageBox.Yes:
            return

        motivo, confirmou = QInputDialog.getText(
            self,
            "Motivo do Cancelamento",
            "Descreva o motivo do cancelamento (opcional):",
        )

        if not confirmou:
            return

        response = cancelar_venda(venda["id"], motivo.strip() or None)

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Venda cancelada com sucesso.")
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
