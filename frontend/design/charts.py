from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from utils.formatacao import formatar_moeda


class GraficoArea(QWidget):
    """Gráfico de área simples desenhado com QPainter — mesma
    abordagem já usada em telas/visao_geral.py (decisão deliberada do
    projeto de não depender de QtCharts, pra não arriscar mais um
    componente pra empacotar), só que reskinado com os tokens novos."""

    def __init__(self, cor=None, parent=None):

        super().__init__(parent)

        self.setMinimumHeight(220)
        self.setMouseTracking(True)

        self.pontos = []
        self.rotulos = []
        self.rotulos_completos = []
        self.cor = cor or tokens.PRIMARIA

        self._coords_tela = []
        self._indice_hover = None

        # estiliza o proprio tooltip do Qt (QToolTip e' global por padrao
        # -- setar no stylesheet DESTE widget o limita a quando o
        # tooltip nasce a partir dele, sem vazar pro resto do app)
        self.setStyleSheet(f"""
            QToolTip {{
                background: {tokens.TEXTO};
                color: {tokens.TEXTO_CLARO};
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: {tokens.TAMANHO_XS}px;
            }}
        """)

    def definir_dados(self, rotulos, valores, rotulos_completos=None):
        """rotulos_completos e' opcional -- rótulo mais descritivo
        (ex.: "Terça-feira") mostrado só no tooltip do hover; sem ele,
        cai no mesmo rótulo curto do eixo."""

        self.rotulos = rotulos
        self.pontos = valores
        self.rotulos_completos = rotulos_completos or rotulos
        self._indice_hover = None

        self.update()

    def mouseMoveEvent(self, event):

        if not self._coords_tela:
            return super().mouseMoveEvent(event)

        pos = event.position()
        x = pos.x()

        indice = min(
            range(len(self._coords_tela)),
            key=lambda i: abs(self._coords_tela[i][0] - x),
        )

        if abs(self._coords_tela[indice][0] - x) > 40:
            if self._indice_hover is not None:
                self._indice_hover = None
                self.update()
            QToolTip.hideText()
            return super().mouseMoveEvent(event)

        if indice != self._indice_hover:
            self._indice_hover = indice
            self.update()

        rotulo = (
            self.rotulos_completos[indice]
            if indice < len(self.rotulos_completos)
            else self.rotulos[indice]
        )
        valor = formatar_moeda(self.pontos[indice])

        QToolTip.showText(
            event.globalPosition().toPoint(),
            f"{rotulo}\n{valor}",
            self,
        )

        return super().mouseMoveEvent(event)

    def leaveEvent(self, event):

        if self._indice_hover is not None:
            self._indice_hover = None
            self.update()

        super().leaveEvent(event)

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

        self._coords_tela = []

        for i, valor in enumerate(self.pontos):

            x, y = coord(i, valor)
            self._coords_tela.append((x, y))

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

        # linha-guia + ponto destacado no indice em hover -- desenhado
        # por cima de tudo, so' quando o mouse esta' perto o bastante
        # de um ponto (ver mouseMoveEvent)
        if self._indice_hover is not None and self._indice_hover < len(self._coords_tela):

            x_hover, y_hover = self._coords_tela[self._indice_hover]

            pen_guia = QPen(QColor(tokens.BORDA_FORTE))
            pen_guia.setWidth(1)
            pen_guia.setStyle(Qt.DashLine)
            painter.setPen(pen_guia)
            painter.drawLine(
                int(x_hover), margem_topo, int(x_hover), margem_topo + area_altura,
            )

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(tokens.CARD))
            painter.drawEllipse(x_hover - 6, y_hover - 6, 12, 12)

            painter.setBrush(cor_linha)
            painter.drawEllipse(x_hover - 4, y_hover - 4, 8, 8)

        painter.end()


class GraficoPizza(QWidget):
    """Anel (donut) simples desenhado com QPainter -- mesma abordagem
    e mesmo motivo de GraficoArea (sem depender de QtCharts). Não
    desenha rótulo/legenda: pensado pra ficar ao lado de uma lista de
    LinhaProgresso/LinhaBarra, que já mostra nome e valor de cada
    fatia com a mesma cor."""

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setMinimumSize(120, 120)

        self._fatias = []

    def definir_dados(self, fatias):
        """fatias: lista de (valor, cor_hex), na mesma ordem/cor da
        legenda externa. Fatias com valor <= 0 são ignoradas."""

        self._fatias = [(valor, cor) for valor, cor in fatias if valor > 0]
        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        lado = min(self.width(), self.height())
        espessura = max(14, lado * 0.18)
        margem = espessura / 2 + 2

        retangulo = QRectF(
            (self.width() - lado) / 2 + margem,
            (self.height() - lado) / 2 + margem,
            lado - margem * 2,
            lado - margem * 2,
        )

        total = sum(valor for valor, _ in self._fatias)

        if not total or retangulo.width() <= 0:
            pen_vazio = QPen(QColor(tokens.BORDA), espessura)
            pen_vazio.setCapStyle(Qt.FlatCap)
            painter.setPen(pen_vazio)
            painter.drawArc(retangulo, 0, 360 * 16)
            painter.end()
            return

        # comeca no topo (12h) e anda em sentido horario -- angulo em
        # 1/16 de grau, como o resto da API de arco do Qt
        angulo_atual = 90 * 16

        for valor, cor in self._fatias:
            extensao = -round(360 * 16 * (valor / total))
            pen = QPen(QColor(cor), espessura)
            pen.setCapStyle(Qt.FlatCap)
            painter.setPen(pen)
            painter.drawArc(retangulo, angulo_atual, extensao)
            angulo_atual += extensao

        painter.end()


class GraficoHeatmap(QWidget):
    """Mapa de calor dia da semana x hora, desenhado com QPainter
    (mesmo motivo de GraficoArea/GraficoPizza -- sem depender de
    QtCharts). Intensidade da cor = valor da célula relativo ao maior
    valor do conjunto (0 = tokens.BORDA, máximo = tokens.PRIMARIA)."""

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setMinimumHeight(240)
        self.setMouseTracking(True)

        # matriz[dia][hora] = {"quantidade": int, "total": float}
        self._matriz = [
            [{"quantidade": 0, "total": 0.0} for _ in range(24)]
            for _ in range(7)
        ]
        self._dias = []
        self._maior_total = 0.0

        self._celula_hover = None

        self.setStyleSheet(f"""
            QToolTip {{
                background: {tokens.TEXTO};
                color: {tokens.TEXTO_CLARO};
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: {tokens.TAMANHO_XS}px;
            }}
        """)

    def definir_dados(self, celulas):
        """celulas: lista de dicts com dia_semana/hora/quantidade/total
        (mesmo formato de GET /relatorios/vendas-dia-semana-hora) --
        ordem de dia_semana tirada da própria primeira ocorrência de
        cada um, pra não depender de acento/grafia exata bater com
        uma lista fixa aqui."""

        dias_em_ordem = []
        matriz_por_dia = {}

        for celula in celulas:
            dia = celula["dia_semana"]
            if dia not in matriz_por_dia:
                dias_em_ordem.append(dia)
                matriz_por_dia[dia] = [
                    {"quantidade": 0, "total": 0.0} for _ in range(24)
                ]
            matriz_por_dia[dia][celula["hora"]] = {
                "quantidade": celula["quantidade"],
                "total": float(celula["total"]),
            }

        self._dias = dias_em_ordem
        self._matriz = [matriz_por_dia[dia] for dia in dias_em_ordem]
        self._maior_total = max(
            (c["total"] for linha in self._matriz for c in linha),
            default=0.0,
        )
        self._celula_hover = None

        self.update()

    def _cor_intensidade(self, total):

        if self._maior_total <= 0:
            return QColor(tokens.BORDA)

        fracao = max(0.0, min(1.0, total / self._maior_total))

        vazio = QColor(tokens.BORDA)
        cheio = QColor(tokens.PRIMARIA)

        return QColor(
            round(vazio.red() + (cheio.red() - vazio.red()) * fracao),
            round(vazio.green() + (cheio.green() - vazio.green()) * fracao),
            round(vazio.blue() + (cheio.blue() - vazio.blue()) * fracao),
        )

    def _geometria(self):

        margem_esq = 48
        margem_baixo = 20
        margem_topo = 4
        margem_dir = 4

        area_largura = self.width() - margem_esq - margem_dir
        area_altura = self.height() - margem_topo - margem_baixo

        n_linhas = len(self._matriz) or 1
        largura_celula = area_largura / 24
        altura_celula = area_altura / n_linhas

        return margem_esq, margem_topo, largura_celula, altura_celula

    def mouseMoveEvent(self, event):

        if not self._matriz:
            return super().mouseMoveEvent(event)

        margem_esq, margem_topo, largura_celula, altura_celula = self._geometria()

        pos = event.position()
        coluna = int((pos.x() - margem_esq) / largura_celula) if largura_celula else -1
        linha = int((pos.y() - margem_topo) / altura_celula) if altura_celula else -1

        if not (0 <= coluna < 24 and 0 <= linha < len(self._matriz)):
            if self._celula_hover is not None:
                self._celula_hover = None
                self.update()
            QToolTip.hideText()
            return super().mouseMoveEvent(event)

        if (linha, coluna) != self._celula_hover:
            self._celula_hover = (linha, coluna)
            self.update()

        celula = self._matriz[linha][coluna]
        QToolTip.showText(
            event.globalPosition().toPoint(),
            f"{self._dias[linha]}, {coluna}h\n"
            f"{celula['quantidade']} venda(s) · {formatar_moeda(celula['total'])}",
            self,
        )

        return super().mouseMoveEvent(event)

    def leaveEvent(self, event):

        if self._celula_hover is not None:
            self._celula_hover = None
            self.update()

        super().leaveEvent(event)

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self._matriz:
            painter.end()
            return

        margem_esq, margem_topo, largura_celula, altura_celula = self._geometria()

        fonte = self.font()
        fonte.setPixelSize(tokens.TAMANHO_XS)
        painter.setFont(fonte)

        for linha, dia in enumerate(self._dias):

            y = margem_topo + linha * altura_celula

            painter.setPen(QColor(tokens.TEXTO_TERCIARIO))
            painter.drawText(
                0, int(y), margem_esq - 8, int(altura_celula),
                Qt.AlignRight | Qt.AlignVCenter,
                dia[:3],
            )

            for hora in range(24):

                x = margem_esq + hora * largura_celula
                celula = self._matriz[linha][hora]

                retangulo = QRectF(
                    x + 1, y + 1, largura_celula - 2, altura_celula - 2,
                )

                cor = self._cor_intensidade(celula["total"])
                painter.setPen(Qt.NoPen)
                painter.setBrush(cor)
                painter.drawRoundedRect(retangulo, 2, 2)

                if self._celula_hover == (linha, hora):
                    pen_destaque = QPen(QColor(tokens.TEXTO), 1.5)
                    painter.setPen(pen_destaque)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRoundedRect(retangulo, 2, 2)

        area_altura_total = len(self._dias) * altura_celula
        painter.setPen(QColor(tokens.TEXTO_TERCIARIO))

        for hora in range(0, 24, 3):
            x = margem_esq + hora * largura_celula
            painter.drawText(
                int(x), int(margem_topo + area_altura_total + 2),
                int(largura_celula * 3), 16,
                Qt.AlignLeft | Qt.AlignTop,
                f"{hora}h",
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
