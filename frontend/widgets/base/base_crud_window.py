from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
)

from widgets.toolbar.crud_toolbar import CrudToolbar
from widgets.tables.standard_table import StandardTable


class BaseCRUDWindow(QWidget):
    """
    Janela base para telas de CRUD.
    Subclasses devem definir `titulo`, `colunas`, `campos` e
    implementar os métodos carregar, novo, editar, excluir e filtrar.
    """

    titulo = ""
    colunas = []
    campos = []

    # Legenda padrão de atalhos — subclasses podem sobrescrever quando os
    # botões/ações da tela tiverem rótulos diferentes (ex.: Vendas).
    atalhos_texto = (
        "⌨ F5 Atualizar   •   Ctrl+N Novo   •   "
        "Delete Excluir   •   Duplo clique Editar"
    )

    def __init__(self):
        super().__init__()

        self.registros = []

        layout = QVBoxLayout(self)

        titulo_lbl = QLabel(self.titulo)
        titulo_lbl.setAlignment(Qt.AlignCenter)
        titulo_lbl.setStyleSheet("font-size:24px; font-weight:bold;")
        layout.addWidget(titulo_lbl)

        pesquisa_layout = QHBoxLayout()
        self.pesquisa = QLineEdit()
        self.pesquisa.setPlaceholderText("Pesquisar...")
        pesquisa_layout.addWidget(self.pesquisa)
        layout.addLayout(pesquisa_layout)

        self.toolbar = CrudToolbar()
        layout.addWidget(self.toolbar)

        self.legenda_atalhos = QLabel(self.atalhos_texto)
        self.legenda_atalhos.setStyleSheet("color:#888; font-size:11px;")
        layout.addWidget(self.legenda_atalhos)

        self.tabela = StandardTable(self.colunas)
        layout.addWidget(self.tabela)

        self.pesquisa.textChanged.connect(self.filtrar)
        self.toolbar.atualizar.connect(self.carregar)
        self.toolbar.novo.connect(self.novo)
        self.toolbar.editar.connect(self.editar)
        self.toolbar.excluir.connect(self.excluir)

        self.carregar()

    # ==========================================
    # MÉTODOS A SEREM IMPLEMENTADOS PELAS SUBCLASSES
    # ==========================================
    def carregar(self):
        """Busca os registros (ex.: no banco) e popula self.registros e a tabela."""
        raise NotImplementedError(
            f"{type(self).__name__} precisa implementar carregar()"
        )

    def filtrar(self):
        """Filtra self.registros conforme o texto em self.pesquisa e atualiza a tabela."""
        raise NotImplementedError(
            f"{type(self).__name__} precisa implementar filtrar()"
        )

    def novo(self):
        """Abre a tela/diálogo de criação de um novo registro."""
        raise NotImplementedError(
            f"{type(self).__name__} precisa implementar novo()"
        )

    def editar(self):
        """Abre a tela/diálogo de edição do registro selecionado na tabela."""
        raise NotImplementedError(
            f"{type(self).__name__} precisa implementar editar()"
        )

    def excluir(self):
        """Remove o registro selecionado na tabela (com confirmação)."""
        raise NotImplementedError(
            f"{type(self).__name__} precisa implementar excluir()"
        )