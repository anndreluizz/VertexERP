"""Peças reutilizáveis pro ciclo carregando/erro/vazio de uma lista
carregada de forma assíncrona (ver services/worker.py) -- construídas
uma vez aqui em vez de reinventadas tela por tela.

`PainelErro`: mensagem + botão "Tentar novamente" (não existia
nenhum padrão de retry em lugar nenhum do app antes disso).

`linhas_esqueleto_tabela`: preenche um QTableWidget com barras cinza
estáticas do tamanho das colunas reais, antecipando o layout antes do
dado chegar -- sem "shimmer"/pulso de propósito: nenhuma animação aqui
significa nada pra desligar quando o usuário tem "Mostrar animações"
desligado (ver utils/acessibilidade.movimento_reduzido), e o ganho
visual do pulso sobre a barra estática é pequeno pra alguém que só vai
ver isso por uma fração de segundo na rede normal."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.icons import icone_pixmap
from design.widgets import BotaoSecundario


class PainelErro(QWidget):
    """Substitui o conteúdo de uma lista quando o carregamento falha --
    diferente do estado "vazio" (carregou certinho, só não tem
    registro nenhum): aqui a chamada de rede não voltou com sucesso, e
    a diferença importa pro usuário (ver PainelErro.definir_mensagem)."""

    tentar_novamente = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        self._icone = QLabel()
        self._icone.setAlignment(Qt.AlignCenter)
        self._icone.setPixmap(icone_pixmap("alert-triangle", cor=tokens.ERRO, tamanho=32))
        layout.addWidget(self._icone)

        self._mensagem = QLabel("Não foi possível carregar.")
        self._mensagem.setAlignment(Qt.AlignCenter)
        self._mensagem.setWordWrap(True)
        self._mensagem.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_MD}px;
        """)
        layout.addWidget(self._mensagem)

        linha_botao = QHBoxLayout()
        linha_botao.setAlignment(Qt.AlignCenter)

        self.bt_tentar_novamente = BotaoSecundario(
            "Tentar novamente", icone_nome="refresh-cw"
        )
        self.bt_tentar_novamente.clicked.connect(self.tentar_novamente.emit)
        linha_botao.addWidget(self.bt_tentar_novamente)

        layout.addLayout(linha_botao)

        self.hide()

    def definir_mensagem(self, mensagem: str):
        self._mensagem.setText(mensagem)


def cartoes_esqueleto(grid_layout, n=6, colunas=3, altura=150):
    """Mesma ideia de linhas_esqueleto_tabela, pra grids de card (ex.:
    tela de Clientes) em vez de QTableWidget -- limpa o grid e
    preenche com N placeholders cinza do tamanho aproximado de um card
    real, antecipando o layout final."""

    while grid_layout.count():
        item = grid_layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()

    for indice in range(n):
        placeholder = QWidget()
        placeholder.setFixedHeight(altura)
        placeholder.setStyleSheet(f"""
            background:{tokens.CARD};
            border:1px solid {tokens.BORDA};
            border-radius:{tokens.RADIUS_LG}px;
        """)

        miolo = QVBoxLayout(placeholder)
        miolo.setContentsMargins(20, 20, 20, 20)
        miolo.setSpacing(10)

        for largura in (0.6, 0.4, 0.8):
            barra = QWidget()
            barra.setFixedHeight(12)
            barra.setStyleSheet(f"""
                background:{tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            """)
            linha = QHBoxLayout()
            linha.addWidget(barra, stretch=int(largura * 100))
            linha.addStretch(int((1 - largura) * 100))
            miolo.addLayout(linha)

        grid_layout.addWidget(placeholder, indice // colunas, indice % colunas)


def linhas_esqueleto_tabela(tabela, colunas_texto, n_linhas=6):
    """Preenche `tabela` (QTableWidget) com `n_linhas` barras cinza
    estáticas nas colunas de `colunas_texto` (índices que normalmente
    têm texto/valor -- colunas de checkbox/foto/ação ficam em branco,
    não tem o que antecipar nelas). Chamar de novo com dado real (via
    setItem normal) sobrescreve essas linhas."""

    tabela.setRowCount(n_linhas)

    for linha in range(n_linhas):
        for coluna in colunas_texto:
            item = QTableWidgetItem()
            item.setFlags(Qt.NoItemFlags)
            item.setBackground(Qt.transparent)
            tabela.setItem(linha, coluna, item)

            barra = QWidget()
            barra.setStyleSheet(f"""
                background:{tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            """)
            barra.setFixedHeight(14)

            wrapper = QWidget()
            wrapper_layout = QHBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(8, 0, 8, 0)
            wrapper_layout.addWidget(barra)

            tabela.setCellWidget(linha, coluna, wrapper)
