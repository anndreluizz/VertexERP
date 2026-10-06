from PySide6.QtWidgets import QMessageBox

from services.centro_custo_service import (
    listar_centros_custo,
    cadastrar_centro_custo,
    atualizar_centro_custo,
    excluir_centro_custo,
)
from services.worker import rodar_em_thread
from services import api

from design.widgets import DialogoGerenciar, pedir_texto


class GerenciarCentrosCustoDialog(DialogoGerenciar):
    """Mesmo padrao de GerenciarCategoriasDespesaDialog -- centro de
    custo agrupa despesas por area/departamento (ver
    ContaPagar.centro_custo)."""

    def __init__(self, parent=None):
        super().__init__(
            "Centros de Custo", "Separe as despesas por setor ou área da loja", "bar-chart-2",
            "Novo centro de custo...", "centro de custo", "centros de custo",
            maiusculas=False, parent=parent,
        )

        self.centros = []
        self._carregando = False

        if not api.usuario_tem_permissao("centros_custo.excluir"):
            self.bt_excluir.setVisible(False)

        self.carregar()

    # ======================================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            listar_centros_custo,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_adicionar.setEnabled(not carregando)
        self.bt_editar.setEnabled(not carregando)
        self.bt_excluir.setEnabled(not carregando)

    def _ao_carregar_sucesso(self, centros):

        self.centros = centros

        self.preencher_nomes([centro.get("nome", "") for centro in self.centros])

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar os centros de custo.\n{erro}")

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def _centro_selecionado(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(
                self, "Aviso", "Selecione um centro de custo."
            )
            return None

        return self.centros[linha]

    def adicionar(self):

        nome = self.novo_nome.text().strip()

        if not nome:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            cadastrar_centro_custo,
            nome,
            ao_sucesso=self._ao_adicionar_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_adicionar_sucesso(self, response):
        if response.status_code == 200:
            self.novo_nome.clear()
            self.carregar()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutacao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutacao_finalizada(self):
        if not self._carregando:
            self._definir_controles_carregando(False)

    def editar(self):

        centro = self._centro_selecionado()

        if centro is None:
            return

        novo_nome, ok = pedir_texto(
            self, "Editar centro de custo", "Nome do centro de custo",
            centro.get("nome", ""), maiusculas=False,
        )

        if not ok:
            return

        novo_nome = novo_nome.strip()

        if not novo_nome:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            atualizar_centro_custo,
            centro["id"],
            novo_nome,
            ao_sucesso=self._ao_editar_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_editar_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def excluir(self):

        centro = self._centro_selecionado()

        if centro is None:
            return

        resposta = QMessageBox.question(
            self,
            "Excluir centro de custo",
            f"Excluir o centro de custo \"{centro.get('nome')}\"?",
        )

        if resposta != QMessageBox.Yes:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            excluir_centro_custo,
            centro["id"],
            ao_sucesso=self._ao_excluir_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_excluir_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
