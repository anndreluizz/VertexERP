"""Busca rapida (Ctrl K) do Vertex 2.0: acha tela, cliente ou produto de
qualquer lugar. Enter abre; setas escolhem; Esc fecha."""
import unicodedata

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from design import tokens
from utils.formatacao import formatar_moeda

LIMITE_POR_TIPO = 5


def _norm(texto):
    sem_acento = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).lower()


def buscar(termo, telas, clientes, produtos, limite=LIMITE_POR_TIPO):
    """[(secao, rotulo, detalhe, tipo, alvo)] -- telas = [(chave, titulo)],
    clientes/produtos = dicts da API. Sem acento e sem maiuscula; o que
    COMECA com o termo vem antes do que so' contem."""
    t = _norm(termo).strip()
    if not t:
        return []

    def achar(itens, chave_texto, extra=lambda _i: ""):
        comeca, contem = [], []
        for item in itens:
            nome = _norm(chave_texto(item))
            if nome.startswith(t) or _norm(extra(item)).startswith(t):
                comeca.append(item)
            elif t in nome:
                contem.append(item)
        return (comeca + contem)[:limite]

    resultado = []
    for chave, titulo in achar(telas, lambda i: i[1]):
        resultado.append(("TELAS", titulo, "Abrir a tela", "tela", chave))
    for c in achar(clientes, lambda c: c.get("nome"), lambda c: c.get("telefone") or ""):
        resultado.append(("CLIENTES", c.get("nome", ""), c.get("telefone") or "Abrir a ficha", "cliente", c))
    for p in achar(produtos, lambda p: p.get("nome"), lambda p: p.get("codigo_barras") or ""):
        detalhe = f"{formatar_moeda(p.get('preco_venda') or 0)} · {p.get('estoque', 0):g} em estoque"
        resultado.append(("PRODUTOS", p.get("nome", ""), detalhe, "produto", p))
    return resultado


class BuscaRapida(QDialog):

    escolhido = Signal(str, object)  # tipo ("tela"|"cliente"|"produto"), alvo

    def __init__(self, telas, clientes, produtos, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(640)
        self._telas, self._clientes, self._produtos = telas, clientes, produtos

        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        corpo = QFrame()
        corpo.setObjectName("corpoBusca")
        corpo.setStyleSheet(f"""
            QFrame#corpoBusca {{ background: {tokens.CARD}; border: 1px solid {tokens.BORDA};
                                 border-radius: {tokens.RADIUS_LG}px; }}
        """)
        externo.addWidget(corpo)
        layout = QVBoxLayout(corpo)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(8)

        self.campo = QLineEdit()
        self.campo.setPlaceholderText("Buscar cliente, produto ou tela…")
        self.campo.setStyleSheet(f"""
            QLineEdit {{ border: none; border-bottom: 1px solid {tokens.BORDA};
                         padding: 8px 4px; font-size: 18px; color: {tokens.TEXTO};
                         background: transparent; }}
        """)
        self.campo.textChanged.connect(self._atualizar)
        self.campo.returnPressed.connect(self._abrir_atual)
        self.campo.installEventFilter(self)
        layout.addWidget(self.campo)

        self.lista = QListWidget()
        self.lista.setMinimumHeight(320)
        self.lista.setStyleSheet(f"""
            QListWidget {{ border: none; background: transparent; font-size: {tokens.TAMANHO_MD}px;
                           color: {tokens.TEXTO}; outline: 0; }}
            QListWidget::item {{ padding: 8px 10px; border-radius: {tokens.RADIUS_SM}px; }}
            QListWidget::item:selected {{ background: {tokens.PRIMARIA_CLARA}; color: {tokens.TEXTO}; }}
        """)
        self.lista.itemActivated.connect(lambda _i: self._abrir_atual())
        layout.addWidget(self.lista)

        self.lbl_dica = QLabel("↑ ↓ para escolher · Enter abre · Esc fecha")
        self.lbl_dica.setStyleSheet(f"color: {tokens.TEXTO_TERCIARIO}; font-size: {tokens.TAMANHO_SM}px;")
        layout.addWidget(self.lbl_dica)

        self._atualizar("")

    def definir_dados(self, clientes, produtos):
        """Chega depois (carregado em segundo plano) -- refaz a lista."""
        self._clientes, self._produtos = clientes, produtos
        self._atualizar(self.campo.text())

    def _atualizar(self, texto):
        self.lista.clear()
        secao_atual = None
        for secao, rotulo, detalhe, tipo, alvo in buscar(texto, self._telas, self._clientes, self._produtos):
            if secao != secao_atual:
                cab = QListWidgetItem(secao)
                cab.setFlags(Qt.NoItemFlags)
                cab.setForeground(Qt.gray)
                self.lista.addItem(cab)
                secao_atual = secao
            item = QListWidgetItem(f"{rotulo}     {detalhe}")
            item.setData(Qt.UserRole, (tipo, alvo))
            self.lista.addItem(item)
        self._selecionar(0, 1)
        if texto and not self.lista.count():
            self.lista.addItem(QListWidgetItem("Nada encontrado"))

    def _selecionar(self, inicio, passo):
        total = self.lista.count()
        i = inicio
        while 0 <= i < total:
            if self.lista.item(i).flags() & Qt.ItemIsSelectable:
                self.lista.setCurrentRow(i)
                return
            i += passo

    def _abrir_atual(self):
        item = self.lista.currentItem()
        dados = item.data(Qt.UserRole) if item else None
        if dados:
            self.accept()
            self.escolhido.emit(*dados)

    def eventFilter(self, obj, evento):
        if obj is self.campo and evento.type() == evento.Type.KeyPress:
            if evento.key() == Qt.Key_Down:
                self._selecionar(self.lista.currentRow() + 1, 1)
                return True
            if evento.key() == Qt.Key_Up:
                self._selecionar(self.lista.currentRow() - 1, -1)
                return True
        return super().eventFilter(obj, evento)

    def abrir_sobre(self, janela):
        self.adjustSize()
        topo = janela.mapToGlobal(janela.rect().topLeft())
        self.move(topo.x() + (janela.width() - self.width()) // 2, topo.y() + 90)
        self.campo.setFocus()
        self.exec()
