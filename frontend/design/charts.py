from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from design import tokens


class GraficoArea(QWidget):
    """Gráfico de área simples desenhado com QPainter — mesma
    abordagem já usada em telas/visao_geral.py (decisão deliberada do
    projeto de não depender de QtCharts, pra não arriscar mais um
    componente pra empacotar), só que reskinado com os tokens novos."""

    def __init__(self, cor=None, parent=None):

        super().__init__(parent)

        self.setMinimumHeight(220)
        self.pontos = []
        self.rotulos = []
        self.cor = cor or tokens.PRIMARIA

    def definir_dados(self, rotulos, valores):

        self.rotulos = rotulos
        self.pontos = valores

        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        largura = self.width()
        altura = self.height()

        margem_esq = 64
        margem_dir = 16
        margem_topo = 16
        margem_baixo = 28

        area_largura = largura - margem_esq - margem_dir
        area_altura = altura - margem_topo - margem_baixo

        maior_valor = max(self.pontos) if self.pontos else 0

        if maior_valor <= 0:
            maior_valor = 1

        pen_grade = QPen(QColor(tokens.BORDA))
        pen_grade.setWidth(1)
        painter.setPen(pen_grade)

        fonte = self.font()
        fonte.setPixelSize(tokens.TAMANHO_XS)
        painter.setFont(fonte)

        for i in range(4):
            y = margem_topo + area_altura * i / 3
            painter.drawLine(margem_esq, int(y), largura - margem_dir, int(y))

            valor_linha = maior_valor * (3 - i) / 3
            painter.setPen(QColor(tokens.TEXTO_TERCIARIO))
            painter.drawText(
                0, int(y) - 8, margem_esq - 10, 16,
                Qt.AlignRight | Qt.AlignVCenter,
                f"R${valor_linha:,.0f}".replace(",", "."),
            )
            painter.setPen(pen_grade)

        if not self.pontos or len(self.pontos) < 2:
            painter.end()
            return

        n = len(self.pontos)
        passo_x = area_largura / (n - 1)

        def coord(i, valor):
            x = margem_esq + i * passo_x
            y = margem_topo + area_altura * (1 - (valor / maior_valor))
            return x, y

        caminho_area = QPainterPath()
        caminho_linha = QPainterPath()

        for i, valor in enumerate(self.pontos):

            x, y = coord(i, valor)

            if i == 0:
                caminho_area.moveTo(x, margem_topo + area_altura)
                caminho_area.lineTo(x, y)
                caminho_linha.moveTo(x, y)
            else:
                caminho_area.lineTo(x, y)
                caminho_linha.lineTo(x, y)

        ultimo_x, _ = coord(n - 1, self.pontos[-1])
        caminho_area.lineTo(ultimo_x, margem_topo + area_altura)
        caminho_area.closeSubpath()

        cor_linha = QColor(self.cor)

        gradiente = QLinearGradient(0, margem_topo, 0, altura - margem_baixo)
        gradiente.setColorAt(0, QColor(cor_linha.red(), cor_linha.green(), cor_linha.blue(), 70))
        gradiente.setColorAt(1, QColor(cor_linha.red(), cor_linha.green(), cor_linha.blue(), 0))

        painter.fillPath(caminho_area, gradiente)

        pen_linha = QPen(cor_linha)
        pen_linha.setWidth(2)
        pen_linha.setCapStyle(Qt.RoundCap)
        pen_linha.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen_linha)
        painter.drawPath(caminho_linha)

        painter.setPen(QColor(tokens.TEXTO_TERCIARIO))

        passo_rotulo = max(1, n // 8)

        for i, rotulo in enumerate(self.rotulos):
            if i % passo_rotulo != 0 and i != n - 1:
                continue
            x, _ = coord(i, self.pontos[i])
            painter.drawText(
                int(x) - 24, altura - margem_baixo + 6, 48, 18,
                Qt.AlignCenter,
                rotulo,
            )

        painter.end()


class LinhaProgresso(QFrame):
    """Linha 'título / valor' com barra de progresso — usada em rankings
    (top produtos, mix de formas de pagamento etc.)."""

    def __init__(self, titulo, subtitulo, valor_texto, percentual, cor=None, parent=None):

        super().__init__(parent)

        cor = cor or tokens.PRIMARIA

        self.setStyleSheet("QFrame { background: transparent; border: none; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        topo = QHBoxLayout()
        topo.setSpacing(8)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(0)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_BASE}px; font-weight:600;
        """)
        col_texto.addWidget(lbl_titulo)

        if subtitulo:
            lbl_sub = QLabel(subtitulo)
            lbl_sub.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_XS}px;
            """)
            col_texto.addWidget(lbl_sub)

        topo.addLayout(col_texto)
        topo.addStretch()

        lbl_valor = QLabel(valor_texto)
        lbl_valor.setStyleSheet(f"""
            background:transparent; color:{cor};
            font-size:{tokens.TAMANHO_BASE}px; font-weight:700;
        """)
        topo.addWidget(lbl_valor)

        layout.addLayout(topo)

        barra_fundo = QFrame()
        barra_fundo.setFixedHeight(6)
        barra_fundo.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:3px; border:none;
        """)

        barra_layout = QHBoxLayout(barra_fundo)
        barra_layout.setContentsMargins(0, 0, 0, 0)
        barra_layout.setSpacing(0)

        barra_preenchida = QFrame()
        barra_preenchida.setStyleSheet(f"""
            background:{cor}; border-radius:3px; border:none;
        """)

        largura_relativa = max(0, min(100, round(percentual)))

        barra_layout.addWidget(barra_preenchida, largura_relativa)
        barra_layout.addStretch(max(1, 100 - largura_relativa))

        layout.addWidget(barra_fundo)
