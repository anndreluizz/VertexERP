from services.venda_service import (
    suspender_venda as enviar_suspensao,
    listar_vendas_suspensas,
    excluir_venda_suspensa,
)
from services.worker import rodar_em_thread
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
)
from design import tokens
from design.widgets import (
    BotaoPerigo,
    BotaoPrimario,
)
from utils.formatacao import formatar_moeda, subtotal_item
from telas.pdv.comum import _parse_data


class VendasSuspensasDialog(QDialog):
    """Lista as vendas suspensas (persistidas no backend como
    Venda.status=ABERTA -- sobrevivem a fechar o app e aparecem pra
    qualquer terminal da mesma loja, ver VendaService.suspender/
    listar_suspensas). Permite retomar ou excluir uma venda suspensa.

    `vendas_suspensas` vem de GET /vendas/suspensas -- cada item ja
    traz nome/codigo/estoque atual do produto embutido (ver
    VendaSuspensaResponse no backend), pra retomar nao precisar de
    uma chamada extra por produto."""

    def __init__(self, vendas_suspensas, parent=None):

        super().__init__(parent)

        self.indice_selecionado = None
        self.acao = None

        self.setWindowTitle("Vendas Suspensas")
        self.resize(480, 420)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        titulo = QLabel("Vendas Suspensas")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)
        layout.addWidget(titulo)

        self.lista = QTableWidget()
        self.lista.setColumnCount(1)
        self.lista.horizontalHeader().setVisible(False)
        self.lista.verticalHeader().setVisible(False)
        self.lista.setSelectionBehavior(QTableWidget.SelectRows)
        self.lista.setSelectionMode(QTableWidget.SingleSelection)
        self.lista.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lista.horizontalHeader().setStretchLastSection(True)
        self.lista.setStyleSheet(f"""
            QTableWidget {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                background:{tokens.CARD};
            }}
        """)

        self.lista.setRowCount(len(vendas_suspensas))

        for linha, venda in enumerate(vendas_suspensas):

            total = sum(
                subtotal_item(item["valor_unitario"], item["quantidade"])
                for item in venda["itens"]
            )
            hora_texto = _parse_data(venda["data"]).strftime("%H:%M")

            rotulo = f"Venda #{venda['id']}"
            if venda.get("cliente_nome"):
                rotulo += f" — {venda['cliente_nome']}"

            texto = (
                f"{rotulo}   ·   {len(venda['itens'])} item(ns)   ·   "
                f"{formatar_moeda(total)}   ·   {hora_texto}"
            )

            self.lista.setItem(linha, 0, QTableWidgetItem(texto))

        self.lista.verticalHeader().setDefaultSectionSize(40)

        if self.lista.rowCount() > 0:
            self.lista.selectRow(0)

        layout.addWidget(self.lista, stretch=1)

        rodape = QHBoxLayout()
        rodape.setSpacing(10)

        bt_excluir = BotaoPerigo("Excluir")
        bt_excluir.clicked.connect(self._excluir)

        bt_retomar = BotaoPrimario("Retomar")
        bt_retomar.clicked.connect(self._retomar)

        rodape.addWidget(bt_excluir)
        rodape.addStretch()
        rodape.addWidget(bt_retomar)

        layout.addLayout(rodape)

    def _linha_atual(self):
        linhas = self.lista.selectionModel().selectedRows()
        return linhas[0].row() if linhas else -1

    def _retomar(self):
        linha = self._linha_atual()
        if linha < 0:
            return
        self.indice_selecionado = linha
        self.acao = "retomar"
        self.accept()

    def _excluir(self):
        linha = self._linha_atual()
        if linha < 0:
            return
        self.indice_selecionado = linha
        self.acao = "excluir"
        self.accept()


class VendasSuspensasMixin:
    """Suspender venda e retomar vendas suspensas."""

    # ==================================================
    # VENDA SUSPENSA (pré-venda) — persistida no backend como
    # Venda.status=ABERTA (ver VendaService.suspender/listar_suspensas/
    # excluir_suspensa): sobrevive a fechar o app e aparece pra
    # qualquer terminal logado na mesma loja, não só neste PDV.
    # ==================================================

    def suspender_venda(self):

        if self._suspendendo_venda:
            return

        if not self.itens:
            QMessageBox.warning(
                self, "Aviso", "Não há itens no carrinho pra suspender."
            )
            return

        self._suspendendo_venda = True
        self.bt_suspender.setEnabled(False)
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        desconto_liquido = self.desconto_valor - self.acrescimo_valor

        rodar_em_thread(
            self,
            enviar_suspensao,
            self.itens,
            cliente_id=self.cliente_id,
            desconto=desconto_liquido,
            ao_sucesso=self._ao_suspender_sucesso,
            ao_erro=self._ao_suspender_erro,
            ao_finalizar=self._ao_suspender_finalizada,
        )

    def _ao_suspender_sucesso(self, response):

        if response.status_code != 201:

            try:
                erro = response.json()
                erro = erro.get("detail", str(erro)) if isinstance(erro, dict) else erro
            except Exception:
                erro = response.text

            QMessageBox.critical(
                self, "Erro", f"Não foi possível suspender a venda.\n\n{erro}"
            )
            return

        self.limpar_venda()
        self._atualizar_contagem_suspensas()

        QMessageBox.information(
            self,
            "Venda suspensa",
            'Use "Vendas Suspensas" pra retomar de onde parou.',
        )

    def _ao_suspender_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_suspender_finalizada(self):
        self._suspendendo_venda = False
        self.bt_suspender.setEnabled(True)
        QApplication.restoreOverrideCursor()

    def abrir_vendas_suspensas(self):

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        rodar_em_thread(
            self,
            listar_vendas_suspensas,
            ao_sucesso=self._ao_listar_suspensas_sucesso,
            ao_erro=self._ao_listar_suspensas_erro,
            ao_finalizar=self._ao_listar_suspensas_finalizada,
        )

    def _ao_listar_suspensas_finalizada(self):
        QApplication.restoreOverrideCursor()

    def _ao_listar_suspensas_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar as vendas suspensas.\n{erro}"
        )

    def _ao_listar_suspensas_sucesso(self, vendas_suspensas):

        dialogo = VendasSuspensasDialog(vendas_suspensas, parent=self)

        if dialogo.exec() != QDialog.Accepted or dialogo.indice_selecionado is None:
            return

        venda = vendas_suspensas[dialogo.indice_selecionado]

        if dialogo.acao == "excluir":
            rodar_em_thread(
                self,
                excluir_venda_suspensa,
                venda["id"],
                ao_sucesso=self._ao_excluir_suspensa_manual_sucesso,
                ao_erro=self._ao_listar_suspensas_erro,
            )
            return

        if self.itens:
            QMessageBox.warning(
                self,
                "Aviso",
                "Finalize, cancele ou suspenda a venda atual antes de "
                "retomar outra.",
            )
            return

        # "codigo"/"estoque" vem None quando o produto foi excluido
        # depois da venda ter sido suspensa -- QTableWidgetItem(None)
        # quebra, e o proprio atualizar_tabela/checagem de estoque
        # esperam string/int normais
        self.itens = [
            {
                "id": item["produto_id"],
                "codigo": item["codigo"] or "",
                "nome": item["nome"],
                "preco": float(item["valor_unitario"]),
                "quantidade": item["quantidade"],
                "unidade": item.get("unidade") or "UN",
                "estoque": item["estoque"] or 0,
            }
            for item in venda["itens"]
        ]
        self.atualizar_tabela()

        if venda["cliente_id"]:
            self.definir_cliente({
                "id": venda["cliente_id"],
                "nome": venda["cliente_nome"],
            })
        else:
            self.limpar_cliente()

        desconto_liquido = float(venda["desconto"])
        self.campo_desconto.setText(
            f"{desconto_liquido:.2f}" if desconto_liquido >= 0 else ""
        )
        self.campo_acrescimo.setText(
            f"{-desconto_liquido:.2f}" if desconto_liquido < 0 else ""
        )
        self.bloco_ajuste.setVisible(desconto_liquido != 0)

        # a venda ja foi retomada pro carrinho local -- apaga o
        # rascunho no servidor pra nao ficar duplicada na lista (falha
        # aqui nao desfaz a retomada, so' deixa o rascunho orfao pra
        # ser limpo manualmente depois, daí o erro silencioso)
        rodar_em_thread(
            self,
            excluir_venda_suspensa,
            venda["id"],
            ao_sucesso=self._ao_excluir_suspensa_sucesso,
            ao_erro=self._ignorar_erro,
        )

    def _ao_excluir_suspensa_manual_sucesso(self, response):

        if response.status_code != 200:
            try:
                erro = response.json()
                erro = erro.get("detail", str(erro)) if isinstance(erro, dict) else erro
            except Exception:
                erro = response.text

            QMessageBox.critical(
                self, "Erro", f"Não foi possível excluir a venda suspensa.\n\n{erro}"
            )
            return

        self._atualizar_contagem_suspensas()

    def _ao_excluir_suspensa_sucesso(self, response):
        # cleanup silencioso do rascunho apos retomar (ver
        # _ao_listar_suspensas_sucesso) -- diferente do handler acima,
        # nao mostra erro pro usuario mesmo se o delete falhar
        self._atualizar_contagem_suspensas()

    def _atualizar_contagem_suspensas(self):

        rodar_em_thread(
            self,
            listar_vendas_suspensas,
            ao_sucesso=self._ao_atualizar_contagem_suspensas_sucesso,
            ao_erro=self._ignorar_erro,
        )

    def _ao_atualizar_contagem_suspensas_sucesso(self, vendas_suspensas):

        total = len(vendas_suspensas)

        self.bt_retomar.setText(
            f"Vendas Suspensas ({total})" if total else "Vendas Suspensas"
        )
        self.bt_retomar.setEnabled(total > 0)
