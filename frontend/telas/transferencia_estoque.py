from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QMessageBox,
    QDialog,
    QTableWidgetItem,
)

from services.produto_service import listar_produtos
from services.loja_service import listar_lojas
from services.estoque_service import listar_transferencias, transferir_estoque
from services.worker import rodar_em_thread, em_paralelo
from widgets.dialogs.pesquisa_window import PesquisaWindow
from design.seletor import Seletor
from telas.estoque_comum import estilo_combo, montar_pagina_movimento
from design import tokens


def _buscar_dados_transferencia():
    """Roda na worker thread -- as 3 chamadas que carregar() precisa,
    independentes entre si, disparadas em paralelo (mesmo padrao de
    ajuste_estoque.py)."""
    produtos, lojas, transferencias = em_paralelo(
        (listar_produtos,), (listar_lojas,), (listar_transferencias,)
    )
    produtos_map = {p["id"]: p["nome"] for p in produtos}
    lojas_map = {l["id"]: l["nome"] for l in lojas}
    return produtos_map, lojas_map, transferencias


class TransferenciaEstoque(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.produto_id = None
        self.lojas = []
        self._carregando = False

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        self.bt_transferir = montar_pagina_movimento(
            self,
            icone_nome="store",
            titulo="Transferência entre Lojas",
            subtitulo="Dá saída na origem e entrada no destino ao mesmo tempo, com registro no histórico.",
            titulo_formulario="Nova transferência",
            rotulo_extra="Loja de destino",
            widget_extra=self._criar_destino(),
            rotulo_acao="Transferir",
            rotulo_quantidade_dica=None,
            placeholder_motivo="Ex.: reposição, redistribuição… (opcional)",
            titulo_historico="Histórico de transferências",
            colunas=["Data", "Produto", "Origem", "Destino", "Quantidade", "Motivo"],
        )

        # ==========================================
        # EVENTOS
        # ==========================================
        self.bt_produto.clicked.connect(self.pesquisar_produto)
        self.bt_transferir.clicked.connect(self.registrar_transferencia)

        self.carregar()

    def _criar_destino(self):
        self.loja_destino = Seletor(campo=True)
        self.loja_destino.setMinimumHeight(44)
        self.loja_destino.setStyleSheet(estilo_combo())
        return self.loja_destino


    # ==========================================
    # PESQUISAR PRODUTO
    # ==========================================
    def pesquisar_produto(self):
        self.bt_produto.setEnabled(False)
        rodar_em_thread(
            self,
            listar_produtos,
            ao_sucesso=self._ao_pesquisar_produto_sucesso,
            ao_erro=self._ao_pesquisar_produto_erro,
            ao_finalizar=self._ao_pesquisar_produto_finalizado,
        )

    def _ao_pesquisar_produto_sucesso(self, produtos):

        tela = PesquisaWindow(
            titulo="Pesquisar Produto",
            colunas=["Código", "Nome", "Categoria", "Estoque"],
            campos=["codigo", "nome", "categoria", "estoque"],
            dados=produtos,
            chave_pesquisa="nome",
        )

        if tela.exec() != QDialog.Accepted:
            return

        self.produto_id = tela.selecionado["id"]

        self.produto.setText(
            f"{tela.selecionado['nome']} "
            f"(estoque atual: {tela.selecionado['estoque']})"
        )

    def _ao_pesquisar_produto_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível buscar produtos.\n{erro}")

    def _ao_pesquisar_produto_finalizado(self):
        self.bt_produto.setEnabled(True)

    # ==========================================
    # CARREGAR (lojas + historico)
    # ==========================================
    def carregar(self):
        if self._carregando:
            return
        self._carregando = True
        self.bt_transferir.setEnabled(False)

        rodar_em_thread(
            self,
            _buscar_dados_transferencia,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _ao_carregar_sucesso(self, resultado):
        try:
            self.produtos_map, self.lojas_map, transferencias = resultado

            self.loja_destino.blockSignals(True)
            self.loja_destino.clear()
            for loja_id, nome in self.lojas_map.items():
                self.loja_destino.addItem(nome, loja_id)
            self.loja_destino.blockSignals(False)

            self.preencher_tabela(transferencias)
        except Exception as erro:
            self._ao_carregar_erro(erro)

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar os dados.\n{erro}")

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self.bt_transferir.setEnabled(True)

    def preencher_tabela(self, transferencias):
        self.tabela.setRowCount(len(transferencias))

        for linha, t in enumerate(transferencias):
            data = datetime.fromisoformat(t["data"]).strftime("%d/%m/%Y %H:%M")

            self.tabela.setItem(linha, 0, QTableWidgetItem(data))
            self.tabela.setItem(
                linha, 1,
                QTableWidgetItem(
                    self.produtos_map.get(t["produto_id"], f"#{t['produto_id']}")
                ),
            )
            self.tabela.setItem(
                linha, 2,
                QTableWidgetItem(
                    self.lojas_map.get(t["loja_origem_id"], f"#{t['loja_origem_id']}")
                ),
            )
            self.tabela.setItem(
                linha, 3,
                QTableWidgetItem(
                    self.lojas_map.get(t["loja_destino_id"], f"#{t['loja_destino_id']}")
                ),
            )
            self.tabela.setItem(
                linha, 4, QTableWidgetItem(str(t["quantidade"]))
            )
            self.tabela.setItem(
                linha, 5, QTableWidgetItem(t.get("motivo") or "")
            )

    # ==========================================
    # REGISTRAR TRANSFERENCIA
    # ==========================================
    def registrar_transferencia(self):
        if self.produto_id is None:
            QMessageBox.warning(self, "Aviso", "Selecione um produto.")
            return

        if self.loja_destino.currentData() is None:
            QMessageBox.warning(self, "Aviso", "Selecione a loja destino.")
            return

        try:
            # 0,350 pra produto por peso (o backend recusa fracao em UN)
            quantidade = float(self.quantidade.text().replace(",", "."))
            if quantidade <= 0:
                raise ValueError

        except ValueError:
            QMessageBox.warning(
                self, "Aviso", "Informe uma quantidade válida."
            )
            return

        dados = {
            "produto_id": self.produto_id,
            "loja_destino_id": self.loja_destino.currentData(),
            "quantidade": quantidade,
            "motivo": self.motivo.text() or None,
        }

        self.bt_transferir.setEnabled(False)

        rodar_em_thread(
            self,
            transferir_estoque,
            dados,
            ao_sucesso=self._ao_registrar_sucesso,
            ao_erro=self._ao_registrar_erro,
            ao_finalizar=self._ao_registrar_finalizado,
        )

    def _ao_registrar_sucesso(self, response):
        if response.status_code == 201:
            QMessageBox.information(
                self, "Sucesso", "Transferência registrada com sucesso."
            )
            self._limpar()
            self.carregar()
        else:
            self._exibir_erro(response)

    def _ao_registrar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_registrar_finalizado(self):
        if not self._carregando:
            self.bt_transferir.setEnabled(True)

    # ==========================================
    # LIMPAR FORMULÁRIO
    # ==========================================
    def _limpar(self):
        self.produto_id = None
        self.produto.clear()
        self.quantidade.clear()
        self.motivo.clear()

    # ==========================================
    # HELPER DE ERRO
    # ==========================================
    def _exibir_erro(self, response):
        try:
            erro = response.json()["detail"]
        except Exception:
            erro = response.text

        QMessageBox.critical(self, "Erro", erro)
