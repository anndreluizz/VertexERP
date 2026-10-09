from PySide6.QtWidgets import QMessageBox

from services.marca_service import (
    listar_marcas,
    criar_marca,
    atualizar_marca,
    excluir_marca,
)
from services.worker import rodar_em_thread
from services import api

from design.widgets import DialogoGerenciar, pedir_texto


def _listar_marcas_ativas():
    return [c for c in listar_marcas() if c.get("ativo", True)]


class GerenciarMarcasDialog(DialogoGerenciar):
    """Mesmo padrao de GerenciarCategoriasDialog/GerenciarCategoriasDespesaDialog
    -- antes desse dialogo, a unica forma de criar uma marca de produto
    era o "+" no cadastro, sem nenhum jeito de corrigir um nome
    digitado errado ou remover uma marca duplicada/nao usada."""

    def __init__(self, parent=None):
        super().__init__(
            "Marcas de Produto", "Marcas usadas no cadastro de produtos", "star",
            "Nova marca...", "marca", "marcas",
            maiusculas=True, parent=parent,
        )

        self.marcas = []
        self._carregando = False

        if not api.usuario_tem_permissao("marcas.excluir"):
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
            _listar_marcas_ativas,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_adicionar.setEnabled(not carregando)
        self.bt_editar.setEnabled(not carregando)
        self.bt_excluir.setEnabled(not carregando)

    def _ao_carregar_sucesso(self, marcas):

        self.marcas = marcas

        self.preencher_nomes([marca.get("nome", "") for marca in self.marcas])

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar as marcas.\n{erro}")

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def _marca_selecionada(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(
                self, "Aviso", "Selecione uma marca."
            )
            return None

        return self.marcas[linha]

    def adicionar(self):

        nome = self.novo_nome.text().strip()

        if not nome:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            criar_marca,
            nome,
            ao_sucesso=self._ao_adicionar_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_adicionar_sucesso(self, response):
        if response.status_code in (200, 201):
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

        marca = self._marca_selecionada()

        if marca is None:
            return

        novo_nome, ok = pedir_texto(
            self, "Editar marca", "Nome da marca",
            marca.get("nome", ""), maiusculas=True,
        )

        if not ok:
            return

        novo_nome = novo_nome.strip().upper()

        if not novo_nome:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            atualizar_marca,
            marca["id"],
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

        marca = self._marca_selecionada()

        if marca is None:
            return

        resposta = QMessageBox.question(
            self,
            "Excluir marca",
            f"Excluir a marca \"{marca.get('nome')}\"?\n\n"
            "Produtos que já usam essa marca não são alterados "
            "-- ela só deixa de aparecer na lista pra novos cadastros.",
        )

        if resposta != QMessageBox.Yes:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            excluir_marca,
            marca["id"],
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
