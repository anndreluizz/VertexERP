from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from design import tokens
from design.animations import fade_in
from design.icons import icone, icone_pixmap
from utils.acessibilidade import movimento_reduzido


# ==========================================
# CARD — superfície elevada padrão do sistema
# ==========================================

class Card(QFrame):
    """Container branco com cantos de 16px e sombra suave — a unidade
    visual básica repetida em quase toda tela do sistema (stat cards,
    linhas de lista, painéis)."""

    def __init__(self, parent=None, elevado=False):

        super().__init__(parent)

        self.setStyleSheet(f"""
            Card {{
                background: {tokens.CARD};
                border-radius: {tokens.RADIUS_LG}px;
                border: 1px solid {tokens.BORDA};
            }}
        """)

        sombra = QGraphicsDropShadowEffect(self)
        sombra.setColor(QColor(tokens.SOMBRA_COR))

        if elevado:
            sombra.setBlurRadius(tokens.SOMBRA_ELEVADA_BLUR)
            sombra.setOffset(0, tokens.SOMBRA_ELEVADA_Y)
            cor = QColor(tokens.SOMBRA_COR)
            cor.setAlpha(tokens.SOMBRA_ELEVADA_ALPHA)
        else:
            sombra.setBlurRadius(tokens.SOMBRA_CARD_BLUR)
            sombra.setOffset(0, tokens.SOMBRA_CARD_Y)
            cor = QColor(tokens.SOMBRA_COR)
            cor.setAlpha(tokens.SOMBRA_CARD_ALPHA)

        sombra.setColor(cor)
        self.setGraphicsEffect(sombra)


# ==========================================
# CARD KPI — indicador com ícone, título e valor
# ==========================================

class CardKPI(Card):
    """Card de indicador executivo (ícone + rótulo + valor grande) —
    usado em grids de KPIs no topo de telas como o Dashboard."""

    def __init__(self, titulo, icone_nome, cor=None, parent=None, destaque=False):

        super().__init__(parent)

        cor = cor or tokens.PRIMARIA

        # destaque=True preenche o card com a cor cheia -- reservado pro
        # numero mais importante de uma grade de KPIs (ex.: Faturamento),
        # pra diferenciar "o dado principal da tela" dos demais em vez de
        # repetir o mesmo card branco pra todos
        if destaque:
            self.setStyleSheet(self.styleSheet() + f"""
                Card {{ background: {cor}; border: none; }}
            """)
            cor_icone_badge = "rgba(255, 255, 255, 0.18)"
            cor_titulo = "rgba(255, 255, 255, 0.85)"
            cor_valor = tokens.TEXTO_CLARO
            cor_icone = tokens.TEXTO_CLARO
            self._destaque = True
        else:
            cor_icone_badge = None
            cor_titulo = tokens.TEXTO_SECUNDARIO
            cor_valor = tokens.TEXTO
            cor_icone = cor
            self._destaque = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        topo = QHBoxLayout()
        topo.setSpacing(8)

        badge_icone = QLabel()
        badge_icone.setFixedSize(36, 36)
        badge_icone.setAlignment(Qt.AlignCenter)

        if cor_icone_badge is None:
            cor_rgb = QColor(cor)
            cor_icone_badge = (
                f"rgba({cor_rgb.red()}, {cor_rgb.green()}, {cor_rgb.blue()}, 0.12)"
            )

        badge_icone.setStyleSheet(f"""
            background: {cor_icone_badge};
            border-radius: {tokens.RADIUS_SM}px;
        """)
        badge_icone.setPixmap(icone_pixmap(icone_nome, cor=cor_icone, tamanho=18))

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setWordWrap(True)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{cor_titulo};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)

        topo.addWidget(badge_icone)
        topo.addWidget(lbl_titulo, stretch=1)

        layout.addLayout(topo)

        self.lbl_valor = QLabel("—")
        self.lbl_valor.setStyleSheet(f"""
            background:transparent; color:{cor_valor};
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)
        layout.addWidget(self.lbl_valor)

        # selo de variacao (ex.: "↑ 12% em relação a ontem") -- comeca
        # oculto; so aparece quando quem usa o card tem um numero de
        # comparacao de verdade pra mostrar (ver definir_variacao)
        self.lbl_variacao = QLabel()
        self.lbl_variacao.setTextFormat(Qt.RichText)
        self.lbl_variacao.setWordWrap(True)
        self.lbl_variacao.setStyleSheet(f"background:transparent; font-size:{tokens.TAMANHO_XS}px;")
        self.lbl_variacao.hide()
        layout.addWidget(self.lbl_variacao)

    def definir_variacao(self, percentual, legenda="em relação a ontem"):
        """Selo colorido de variação percentual abaixo do valor. Chamar
        com percentual=None (o padrão quando não há base de comparação
        confiável -- ver telas/dashboard.py) esconde o selo em vez de
        inventar um número."""

        if percentual is None:
            self.lbl_variacao.hide()
            return

        positiva = percentual >= 0
        seta = "↑" if positiva else "↓"

        # em cima do fundo cheio (destaque=True) verde/vermelho perdem
        # contraste -- usa branco translucido em vez da cor semantica
        cor = (
            "rgba(255, 255, 255, 0.85)" if self._destaque
            else (tokens.SUCESSO if positiva else tokens.ERRO)
        )

        cor_legenda = (
            "rgba(255, 255, 255, 0.6)" if self._destaque else tokens.TEXTO_TERCIARIO
        )
        self.lbl_variacao.setText(
            f'<span style="color:{cor}; font-weight:700;">{seta} {abs(percentual):.0f}%</span> '
            f'<span style="color:{cor_legenda};">{legenda}</span>'
        )
        self.lbl_variacao.show()

    def definir_valor(self, texto):
        # o fade sutil da um "respiro" visual toda vez que o numero
        # muda (carregamento inicial ou um recarregar/filtro) -- sem
        # ficar sub/somando digito por digito, que exigiria parsear de
        # volta pra numero um texto ja formatado (moeda, unidade etc.)
        self.lbl_valor.setText(texto)
        fade_in(self.lbl_valor, duracao=240)


# ==========================================
# SEÇÃO — card com título e corpo substituível
# ==========================================

class SecaoCard(Card):
    """Card com cabeçalho (ícone + título) e um corpo que pode ser
    limpo/repopulado — base de painéis como rankings, gráficos e listas
    (ex.: Top Produtos, Formas de Pagamento, Vendas Recentes)."""

    def __init__(self, titulo, icone_nome=None, widget_acao=None, parent=None):

        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(8)

        if icone_nome:
            lbl_icone = QLabel()
            lbl_icone.setStyleSheet("background:transparent;")
            lbl_icone.setPixmap(
                icone_pixmap(icone_nome, cor=tokens.TEXTO_SECUNDARIO, tamanho=18)
            )
            cabecalho.addWidget(lbl_icone)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_LG}px; font-weight:700;
        """)
        cabecalho.addWidget(lbl_titulo)
        cabecalho.addStretch()

        # widget opcional na ponta direita do cabecalho -- um seletor
        # de periodo, um link "Ver todas", etc. (ex.: Top Produtos e
        # Formas de Pagamento no Dashboard)
        if widget_acao is not None:
            cabecalho.addWidget(widget_acao)

        layout.addLayout(cabecalho)

        self.corpo = QVBoxLayout()
        self.corpo.setSpacing(14)
        layout.addLayout(self.corpo)

    def limpar_corpo(self):

        while self.corpo.count():
            item = self.corpo.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def adicionar_vazio(self, texto):

        lbl = QLabel(texto)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; padding: 16px;
        """)
        self.corpo.addWidget(lbl)


# ==========================================
# BOTÕES — hover com transição de cor animada
# ==========================================

class _BotaoAnimado(QPushButton):

    def __init__(
        self,
        texto="",
        icone_nome=None,
        parent=None,
        cor_normal="#2563EB",
        cor_hover="#1D4ED8",
        cor_texto="#FFFFFF",
        cor_desabilitado="#E5E7EB",
        contorno=False,
        altura=44,
    ):

        super().__init__(texto, parent)

        self._cor_normal = QColor(cor_normal)
        self._cor_hover = QColor(cor_hover)
        self._cor_atual = QColor(cor_normal)
        self._cor_texto = QColor(cor_texto)
        self._cor_desabilitado = QColor(cor_desabilitado)
        self._contorno = contorno
        self._icone_nome = icone_nome

        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(altura)
        self.setFont(QFont(tokens.FONTE_FAMILIA_PADRAO, tokens.TAMANHO_MD))

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(150)
        self._anim.valueChanged.connect(self._ao_animar)

    def enterEvent(self, event):
        if self.isEnabled():
            self._animar_para(self._cor_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.isEnabled():
            self._animar_para(self._cor_normal)
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.update()
        super().focusOutEvent(event)

    def _animar_para(self, cor_destino):
        self._anim.stop()

        if movimento_reduzido():
            self._cor_atual = cor_destino
            self.update()
            return

        self._anim.setStartValue(self._cor_atual)
        self._anim.setEndValue(cor_destino)
        self._anim.start()

    def _ao_animar(self, valor):
        # mesmo caso de widgets/nav_card.py::_ao_animar_sombra: stop()
        # chamado antes da animacao ter rodado alguma vez pode emitir
        # valueChanged(None) -- sem essa guarda, self._cor_atual vira
        # None e o paintEvent quebra ao tentar pintar com isso.
        if valor is None:
            return

        self._cor_atual = valor
        self.update()

    def sizeHint(self):

        metrica = QFontMetrics(self.font())
        largura_texto = metrica.horizontalAdvance(self.text())

        largura = largura_texto + 40

        if self._icone_nome:
            largura += 26

        return QSize(largura, self.minimumHeight())

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        caminho = QPainterPath()
        caminho.addRoundedRect(rect, tokens.RADIUS_SM, tokens.RADIUS_SM)

        if not self.isEnabled():
            painter.fillPath(caminho, self._cor_desabilitado)
            cor_texto = QColor(tokens.TEXTO_TERCIARIO)
        elif self._contorno:
            painter.fillPath(caminho, QColor(tokens.CARD))
            painter.setPen(self._cor_atual)
            painter.drawPath(caminho)
            cor_texto = self._cor_atual
        else:
            painter.fillPath(caminho, self._cor_atual)
            cor_texto = self._cor_texto

        # calcula o bloco (icone + texto) centralizado como grupo
        metrica = QFontMetrics(self.font())
        largura_texto = metrica.horizontalAdvance(self.text())

        largura_grupo = largura_texto
        if self._icone_nome:
            largura_grupo += 24

        x = (self.width() - largura_grupo) / 2
        centro_y = self.height() / 2

        if self._icone_nome:
            pixmap = icone_pixmap(self._icone_nome, cor=cor_texto.name(), tamanho=18)
            painter.drawPixmap(
                int(x), int(centro_y - 9), pixmap
            )
            x += 24

        painter.setPen(cor_texto)
        painter.setFont(self.font())
        painter.drawText(
            QRectF(x, 0, largura_texto + 4, self.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.text(),
        )

        # anel de foco por teclado -- paintEvent e' totalmente custom
        # (sem chamar super().paintEvent), entao o anel padrao do Qt
        # nunca aparecia sozinho; sem isso, navegar por Tab deixava
        # invisivel qual botao estava selecionado antes de apertar
        # Enter/Espaco. Desenhado por dentro da borda (nao por fora) pra
        # nao precisar de espaco extra no layout.
        if self.hasFocus() and self.isEnabled():
            anel = QPainterPath()
            anel.addRoundedRect(
                rect.adjusted(3, 3, -3, -3),
                max(tokens.RADIUS_SM - 3, 2),
                max(tokens.RADIUS_SM - 3, 2),
            )
            cor_anel = self._cor_atual if self._contorno else QColor(tokens.TEXTO_CLARO)
            caneta_foco = QPen(cor_anel)
            caneta_foco.setWidthF(2)
            painter.setPen(caneta_foco)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(anel)

        painter.end()


class BotaoPrimario(_BotaoAnimado):
    def __init__(self, texto="", icone_nome=None, parent=None):
        super().__init__(
            texto, icone_nome, parent,
            cor_normal=tokens.PRIMARIA,
            cor_hover=tokens.PRIMARIA_HOVER,
            cor_texto=tokens.TEXTO_CLARO,
        )


class BotaoSucesso(_BotaoAnimado):
    def __init__(self, texto="", icone_nome=None, parent=None):
        super().__init__(
            texto, icone_nome, parent,
            cor_normal=tokens.SECUNDARIA,
            cor_hover=tokens.SECUNDARIA_HOVER,
            cor_texto=tokens.TEXTO_CLARO,
        )


class BotaoPerigo(_BotaoAnimado):
    def __init__(self, texto="", icone_nome=None, parent=None):
        super().__init__(
            texto, icone_nome, parent,
            cor_normal=tokens.ERRO,
            cor_hover=tokens.ERRO_HOVER,
            cor_texto=tokens.TEXTO_CLARO,
        )


class BotaoSecundario(_BotaoAnimado):
    """Botão contorno (outline) — usado pra ações secundárias, como
    "Cancelar" ao lado de um botão primário."""

    def __init__(self, texto="", icone_nome=None, parent=None):
        super().__init__(
            texto, icone_nome, parent,
            cor_normal=tokens.TEXTO_SECUNDARIO,
            cor_hover=tokens.PRIMARIA,
            cor_texto=tokens.TEXTO_SECUNDARIO,
            contorno=True,
        )


# ==========================================
# BADGE — etiqueta de status colorida
# ==========================================

class Badge(QLabel):

    @staticmethod
    def variantes():
        # funcao (nao dict de classe) de proposito: os valores de
        # tokens.* soh ficam corretos se forem lidos depois que
        # tokens.aplicar() rodou -- um dict fixo no corpo da classe
        # travaria a paleta clara pra sempre, calculado no momento em
        # que este modulo e' importado (que acontece antes do tema
        # escuro ser aplicado, ver app.py)
        return {
            "sucesso": (tokens.SUCESSO_CLARO, tokens.SECUNDARIA_HOVER),
            "alerta": (tokens.ALERTA_CLARO, tokens.ALERTA_TEXTO),
            "erro": (tokens.ERRO_CLARO, tokens.ERRO_HOVER),
            "info": (tokens.PRIMARIA_CLARA, tokens.PRIMARIA_HOVER),
            "neutro": (tokens.FUNDO, tokens.TEXTO_SECUNDARIO),
        }

    def __init__(self, texto, variante="neutro", parent=None):

        super().__init__(texto, parent)

        variantes = Badge.variantes()
        fundo, cor_texto = variantes.get(variante, variantes["neutro"])

        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            background: {fundo};
            color: {cor_texto};
            border-radius: {tokens.RADIUS_PILL}px;
            font-size: {tokens.TAMANHO_XS}px;
            font-weight: 600;
            padding: 3px 10px;
        """)


# ==========================================
# AVATAR — círculo com iniciais
# ==========================================

class Avatar(QLabel):

    CORES_FUNDO = [
        "#DBEAFE", "#DCFCE7", "#FEF3C7", "#FCE7F3", "#EDE9FE", "#FEE2E2",
    ]
    CORES_TEXTO = [
        "#1D4ED8", "#15803D", "#B45309", "#BE185D", "#6D28D9", "#B91C1C",
    ]

    def __init__(self, nome, tamanho=40, parent=None):

        super().__init__(parent)

        indice = sum(ord(c) for c in nome) % len(self.CORES_FUNDO) if nome else 0

        self.setFixedSize(tamanho, tamanho)
        self.setAlignment(Qt.AlignCenter)
        self.setText(self._iniciais(nome))
        self.setStyleSheet(f"""
            background: {self.CORES_FUNDO[indice]};
            color: {self.CORES_TEXTO[indice]};
            border-radius: {tamanho // 2}px;
            font-weight: 700;
            font-size: {max(11, tamanho // 3)}px;
        """)

    @staticmethod
    def _iniciais(nome):

        partes = (nome or "").strip().split()

        if not partes:
            return "?"

        if len(partes) == 1:
            return partes[0][:2].upper()

        return (partes[0][0] + partes[-1][0]).upper()


# ==========================================
# CABEÇALHO DE DIÁLOGO — ícone + título/subtítulo + separador
# ==========================================

class CabecalhoDialogo(QFrame):
    """Cabeçalho padrão de QDialog: chip de ícone colorido, coluna de
    título+subtítulo, botão de fechar opcional e a linha separadora
    logo abaixo -- esse bloco se repetia quase idêntico em cada
    diálogo de cadastro/confirmação (cadastro_despesa.py,
    pagamento_despesa.py, ...), então virou um widget único aqui em
    vez de continuar sendo copiado.

    `titulo`/`icone_cabecalho`/`subtitulo` ficam expostos como
    atributos (via as propriedades .titulo/.subtitulo/.icone) pra quem
    precisa mudá-los depois de construído -- ex.: PagamentoDespesaDialog
    troca ícone/texto quando o pagamento é confirmado (ver
    definir_texto/definir_icone)."""

    def __init__(
        self,
        icone_nome,
        cor,
        cor_fundo,
        titulo,
        subtitulo="",
        tamanho_icone=44,
        tamanho_pixmap=20,
        fechavel=False,
        ao_fechar=None,
        parent=None,
    ):

        super().__init__(parent)

        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        layout_externo.setSpacing(0)

        linha = QHBoxLayout()
        linha.setContentsMargins(24, 20, 24, 16)
        linha.setSpacing(12)

        self.icone = QLabel()
        self.icone.setFixedSize(tamanho_icone, tamanho_icone)
        self.icone.setAlignment(Qt.AlignCenter)
        self.icone.setStyleSheet(f"""
            background:{cor_fundo};
            border-radius:{tokens.RADIUS_MD}px;
        """)
        self.icone.setPixmap(icone_pixmap(icone_nome, cor=cor, tamanho=tamanho_pixmap))

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(2)

        self.titulo = QLabel(titulo)
        self.titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_LG}px; font-weight:800;
        """)

        self.subtitulo = QLabel(subtitulo)
        self.subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_titulo.addWidget(self.titulo)
        col_titulo.addWidget(self.subtitulo)

        linha.addWidget(self.icone)
        linha.addLayout(col_titulo)
        linha.addStretch()

        if fechavel:
            bt_fechar = QPushButton()
            bt_fechar.setFixedSize(32, 32)
            bt_fechar.setCursor(Qt.PointingHandCursor)
            bt_fechar.setAutoDefault(False)
            bt_fechar.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=15))
            # so' icone, sem texto -- sem nome, leitor de tela (Narrator/
            # NVDA) nao tem o que anunciar pra esse botao
            bt_fechar.setToolTip("Fechar")
            bt_fechar.setAccessibleName("Fechar")
            bt_fechar.setStyleSheet(f"""
                QPushButton {{ background:transparent; border:none; border-radius:8px; }}
                QPushButton:hover {{ background:{tokens.FUNDO}; }}
            """)
            if ao_fechar:
                bt_fechar.clicked.connect(ao_fechar)
            linha.addWidget(bt_fechar)

        layout_externo.addLayout(linha)

        separador = QFrame()
        separador.setFixedHeight(1)
        separador.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        layout_externo.addWidget(separador)

    def definir_icone(self, icone_nome, cor, tamanho_pixmap=20):
        self.icone.setPixmap(icone_pixmap(icone_nome, cor=cor, tamanho=tamanho_pixmap))

    def definir_texto(self, titulo, subtitulo=None):
        self.titulo.setText(titulo)
        if subtitulo is not None:
            self.subtitulo.setText(subtitulo)


# ==========================================
# CAMPO DE TEXTO
# ==========================================

class CampoTexto(QLineEdit):

    def __init__(self, placeholder="", parent=None, cor_foco=None):

        super().__init__(parent)

        # cor_foco deixa o campo casar com uma ação/botão adjacente de
        # cor diferente da primária (ex.: campo ao lado de um botão
        # verde de "Adicionar") -- por padrão usa a borda primária, que
        # serve pra maioria dos formulários do sistema.
        cor_foco = cor_foco or tokens.PRIMARIA

        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(44)
        self.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
                padding: 0 14px;
                font-size: {tokens.TAMANHO_MD}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QLineEdit:focus {{
                border: 1.5px solid {cor_foco};
            }}
            QLineEdit:disabled {{
                background: {tokens.FUNDO};
                color: {tokens.TEXTO_TERCIARIO};
            }}
        """)


# ==========================================
# FLOW LAYOUT — grid responsivo que quebra sozinho
# ==========================================

class FlowLayout(QLayout):
    """Adaptação do "Flow Layout" oficial da documentação do Qt (C++)
    pro PySide6 -- um QGridLayout comum tem número fixo de colunas e
    não recalcula isso ao redimensionar a janela; esse layout, ao
    contrário, vai encaixando os itens da esquerda pra direita e quebra
    pra próxima linha sozinho assim que não cabe mais, sem nunca forçar
    rolagem horizontal nem estourar a largura do container.

    Usado nos mini-cards de indicadores da ficha do cliente: em telas
    largas rende como 2 linhas (a ordem de inserção decide o
    agrupamento visual), e vai reorganizando pra mais linhas sozinho se
    a janela ficar mais estreita."""

    def __init__(self, parent=None, margem=0, espaco_h=8, espaco_v=8):

        super().__init__(parent)

        self._espaco_h = espaco_h
        self._espaco_v = espaco_v
        self._itens = []

        self.setContentsMargins(margem, margem, margem, margem)

    def addItem(self, item):
        self._itens.append(item)

    def horizontalSpacing(self):
        return self._espaco_h

    def verticalSpacing(self):
        return self._espaco_v

    def count(self):
        return len(self._itens)

    def itemAt(self, index):
        if 0 <= index < len(self._itens):
            return self._itens[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._itens):
            return self._itens.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, largura):
        return self._montar_layout(QRect(0, 0, largura, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._montar_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):

        tamanho = QSize()

        for item in self._itens:
            tamanho = tamanho.expandedTo(item.minimumSize())

        margens = self.contentsMargins()
        tamanho += QSize(
            margens.left() + margens.right(),
            margens.top() + margens.bottom(),
        )

        return tamanho

    def _montar_layout(self, rect, so_calcular):

        esquerda, topo, direita, baixo = self.getContentsMargins()
        area = rect.adjusted(esquerda, topo, -direita, -baixo)

        x = area.x()
        y = area.y()
        altura_linha = 0

        for item in self._itens:

            tamanho_item = item.sizeHint()
            proximo_x = x + tamanho_item.width() + self._espaco_h

            if proximo_x - self._espaco_h > area.right() and altura_linha > 0:
                x = area.x()
                y = y + altura_linha + self._espaco_v
                proximo_x = x + tamanho_item.width() + self._espaco_h
                altura_linha = 0

            if not so_calcular:
                item.setGeometry(QRect(QPoint(x, y), tamanho_item))

            x = proximo_x
            altura_linha = max(altura_linha, tamanho_item.height())

        return y + altura_linha - rect.y() + baixo
