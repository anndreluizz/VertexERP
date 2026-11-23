from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QMessageBox,
    QDialog,
    QTableWidgetItem,
)

from services.produto_service import listar_produtos
from services.estoque_service import listar_movimentos, ajustar_estoque
from services.worker import rodar_em_thread, em_paralelo
from services import api
from widgets.dialogs.pesquisa_window import PesquisaWindow
from design.seletor import Seletor
from telas.estoque_comum import estilo_combo, montar_pagina_movimento
from design import tokens


def _buscar_historico_estoque():
    """Roda na worker thread -- as 2 chamadas que carregar() precisa,
    independentes entre si, disparadas em paralelo."""
    produtos, movimentos = em_paralelo((listar_produtos,), (listar_movimentos,))
    produtos_map = {p["id"]: p["nome"] for p in produtos}
    return produtos_map, movimentos


def _pode_ajustar():
    # backend exige estoque.ajustar (POST /estoque/movimentos) --
    # sem ela o botao fica desligado em vez de so' dar erro
    return api.usuario_tem_permissao("estoque.ajustar")


class AjusteEstoque(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.produto_id = None
        self._carregando = False

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        self.bt_registrar = montar_pagina_movimento(
            self,
            icone_nome="refresh-cw",
            titulo="Ajuste de Estoque",
            subtitulo="Entradas e saídas manuais com motivo, registradas no histórico.",
            titulo_formulario="Novo ajuste",
            rotulo_extra="Tipo",
            widget_extra=self._criar_tipo(),
            rotulo_acao="Registrar ajuste",
            rotulo_quantidade_dica=None,
            placeholder_motivo="Ex.: inventário, quebra, correção…",
            titulo_historico="Histórico de movimentações",
            colunas=["Data", "Produto", "Tipo", "Quantidade", "Motivo"],
        )

        # ==========================================
        # EVENTOS
        # ==========================================
        self.bt_produto.clicked.connect(self.pesquisar_produto)
        self.bt_registrar.clicked.connect(self.registrar_ajuste)

        self.carregar()

    def _criar_tipo(self):
        self.tipo = Seletor(campo=True)
        self.tipo.addItems(["Entrada", "Saída"])
        self.tipo.setMinimumHeight(44)
        self.tipo.setStyleSheet(estilo_combo())
        return self.tipo


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

        self.definir_produto(tela.selecionado)

    def definir_produto(self, produto):
        """Escolhe o produto do ajuste -- pela pesquisa ou pre-selecionado
        (ex.: botao 'Ajustar estoque' da ficha rapida de Produtos)."""
        self.produto_id = produto["id"]

        self.produto.setText(
            f"{produto['nome']} (estoque atual: {produto['estoque']})"
        )

    def _ao_pesquisar_produto_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível buscar produtos.\n{erro}")

    def _ao_pesquisar_produto_finalizado(self):
        self.bt_produto.setEnabled(True)

    # ==========================================
    # CARREGAR HISTÓRICO
    # ==========================================
    def carregar(self):
        if self._carregando:
            return
        self._carregando = True
        self.bt_registrar.setEnabled(False)

        rodar_em_thread(
            self,
            _buscar_historico_estoque,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _ao_carregar_sucesso(self, resultado):
        try:
            self.produtos_map, self.movimentos = resultado
            self.preencher_tabela(self.movimentos)
        except Exception as erro:
            self._ao_carregar_erro(erro)

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar o histórico.\n{erro}")

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self.bt_registrar.setEnabled(_pode_ajustar())

    def preencher_tabela(self, movimentos):
        self.tabela.setRowCount(len(movimentos))

        for linha, mov in enumerate(movimentos):
            data = datetime.fromisoformat(mov["data"]).strftime("%d/%m/%Y %H:%M")

            self.tabela.setItem(linha, 0, QTableWidgetItem(data))

            self.tabela.setItem(
                linha,
                1,
                QTableWidgetItem(
                    self.produtos_map.get(
                        mov["produto_id"], f"#{mov['produto_id']}"
                    )
                ),
            )

            self.tabela.setItem(
                linha,
                2,
                QTableWidgetItem(
                    "Entrada" if mov["tipo"] == "ENTRADA" else "Saída"
                ),
            )

            self.tabela.setItem(
                linha, 3, QTableWidgetItem(str(mov["quantidade"]))
            )

            self.tabela.setItem(
                linha, 4, QTableWidgetItem(mov.get("motivo") or "")
            )

    # ==========================================
    # REGISTRAR AJUSTE
    # ==========================================
    def registrar_ajuste(self):
        if self.produto_id is None:
            QMessageBox.warning(self, "Aviso", "Selecione um produto.")
            return

        try:
            # 12,5 (kg) ou 3 (un.)
            quantidade = round(float(self.quantidade.text().strip().replace(",", ".")), 3)
            if quantidade <= 0:
                raise ValueError

        except ValueError:
            QMessageBox.warning(
                self, "Aviso", "Informe uma quantidade válida."
            )
            return

        dados = {
            "produto_id": self.produto_id,
            "tipo": "ENTRADA" if self.tipo.currentText() == "Entrada" else "SAIDA",
            "quantidade": quantidade,
            "motivo": self.motivo.text() or None,
        }

        self.bt_registrar.setEnabled(False)

        rodar_em_thread(
            self,
            ajustar_estoque,
            dados,
            ao_sucesso=self._ao_registrar_ajuste_sucesso,
            ao_erro=self._ao_registrar_ajuste_erro,
            ao_finalizar=self._ao_registrar_ajuste_finalizado,
        )

    def _ao_registrar_ajuste_sucesso(self, response):
        if response.status_code == 201:
            QMessageBox.information(
                self, "Sucesso", "Ajuste registrado com sucesso."
            )
            self._limpar()
            self.carregar()
        else:
            self._exibir_erro(response)

    def _ao_registrar_ajuste_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_registrar_ajuste_finalizado(self):
        # se o sucesso ja disparou carregar() de novo, deixa ele mesmo
        # reabilitar (mesmo raciocinio de telas/caixa.py)
        if not self._carregando:
            self.bt_registrar.setEnabled(_pode_ajustar())

    # ==========================================
    # LIMPAR FORMULÁRIO
    # ==========================================
    def _limpar(self):
        self.produto_id = None
        self.produto.clear()
        self.quantidade.clear()
        self.motivo.clear()
        self.tipo.setCurrentIndex(0)

    # ==========================================
    # HELPER DE ERRO
    # ==========================================
    def _exibir_erro(self, response):
        try:
            erro = response.json()["detail"]
        except Exception:
            erro = response.text

        QMessageBox.critical(self, "Erro", erro)
