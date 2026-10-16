from PySide6.QtWidgets import QMessageBox

from PySide6.QtWidgets import (
    QInputDialog,
)


from services.categoria_service import listar_categorias, criar_categoria
from services.marca_service import listar_marcas, criar_marca
from telas.gerenciar_categorias import GerenciarCategoriasDialog
from telas.gerenciar_marcas import GerenciarMarcasDialog
from services.worker import rodar_em_thread


def _criar_categoria_com_nome(nome):
    """Roda na worker thread -- o nome viaja junto com a resposta (nao
    da pra usar lambda/closure como callback, ver services/worker.py)."""
    return criar_categoria(nome), nome


def _criar_marca_com_nome(nome):
    """Mesmo motivo de _criar_categoria_com_nome."""
    return criar_marca(nome), nome


class CategoriasMarcasMixin:
    """Combos de categoria e marca: carregar, criar e gerenciar."""

    # ==========================================
    # CATEGORIAS
    # ==========================================

    def _carregar_categorias(self):

        # preserva o que ja estava selecionado/digitado -- sem isso,
        # recarregar a lista (ex.: depois de fechar "Gerenciar
        # categorias") apagava a categoria que o usuario ja tinha
        # escolhido pro produto em edicao (mesmo padrao ja usado em
        # cadastro_despesa.py pro mesmo tipo de combobox)
        self._categoria_selecionada_pendente = self.categoria.currentText()

        rodar_em_thread(
            self,
            listar_categorias,
            ao_sucesso=self._ao_carregar_categorias_sucesso,
        )

    def _ao_carregar_categorias_sucesso(self, categorias):

        self.categoria.clear()

        for c in categorias:
            if c.get("ativo", True):
                self.categoria.addItem(c["nome"])

        self.categoria.setCurrentText(self._categoria_selecionada_pendente)

    def criar_nova_categoria(self):

        nome, ok = QInputDialog.getText(
            self,
            "Nova Categoria",
            "Nome da nova categoria:"
        )

        if not ok or not nome.strip():
            return

        nome = nome.strip().upper()

        rodar_em_thread(
            self,
            _criar_categoria_com_nome,
            nome,
            ao_sucesso=self._ao_criar_categoria_sucesso,
            ao_erro=self._ao_criar_categoria_erro,
        )

    def _ao_criar_categoria_sucesso(self, resultado):

        response, nome = resultado

        if response.status_code in (200, 201):

            if self.categoria.findText(nome) < 0:
                self.categoria.addItem(nome)

            self.categoria.setCurrentText(nome)

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_criar_categoria_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def gerenciar_categorias(self):

        dialogo = GerenciarCategoriasDialog(parent=self)
        dialogo.exec()

        self._carregar_categorias()

    # ==========================================
    # MARCA
    # ==========================================

    def _carregar_marcas(self):

        # preserva a marca ja selecionada (mesmo motivo de
        # _carregar_categorias) -- guarda o ID, nao o texto, porque o
        # combo de marca nao e' editavel (item sempre tem itemData)
        self._marca_selecionada_pendente = self.marca.currentData()

        rodar_em_thread(
            self,
            listar_marcas,
            ao_sucesso=self._ao_carregar_marcas_sucesso,
        )

    def _ao_carregar_marcas_sucesso(self, marcas):

        self.marca.clear()
        self.marca.addItem("Sem marca", None)

        for m in marcas:
            if m.get("ativo", True):
                self.marca.addItem(m["nome"], m["id"])

        indice = self.marca.findData(self._marca_selecionada_pendente)
        self.marca.setCurrentIndex(indice if indice >= 0 else 0)

    def criar_nova_marca(self):

        nome, ok = QInputDialog.getText(
            self,
            "Nova Marca",
            "Nome da nova marca:"
        )

        if not ok or not nome.strip():
            return

        nome = nome.strip().upper()

        rodar_em_thread(
            self,
            _criar_marca_com_nome,
            nome,
            ao_sucesso=self._ao_criar_marca_sucesso,
            ao_erro=self._ao_criar_marca_erro,
        )

    def _ao_criar_marca_sucesso(self, resultado):

        response, nome = resultado

        if response.status_code in (200, 201):

            marca_id = response.json()["id"]

            if self.marca.findData(marca_id) < 0:
                self.marca.addItem(nome, marca_id)

            self.marca.setCurrentIndex(self.marca.findData(marca_id))

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_criar_marca_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def gerenciar_marcas(self):

        dialogo = GerenciarMarcasDialog(parent=self)
        dialogo.exec()

        self._carregar_marcas()
