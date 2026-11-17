"""Visual novo do login e do primeiro acesso: fundo vivo (auroras, grade de
pontos, parallax), cards animados do painel de marca, botao com estados e
onda de revelacao. Pecas so visuais -- a logica fica em telas/login.py."""
import math
import random

from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QElapsedTimer, QPointF, QRectF, QSize, QEvent
from PySide6.QtGui import (QColor, QPainter, QPainterPath, QLinearGradient, QRadialGradient, QFont, QPen, QBrush,
                           QGuiApplication)
from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton,
                               QCheckBox, QFrame)
from design import tokens
from design.fonts import carregar_fonte_inter, familia_titulo
from design.icons import icone
from utils.acessibilidade import movimento_reduzido

T = tokens
PESOS = {400: QFont.Normal, 500: QFont.Medium, 600: QFont.DemiBold, 700: QFont.Bold, 800: QFont.ExtraBold}


def fonte(px, peso=400, titulo=False):
    f = QFont(familia_titulo() if titulo else QApplication.font().family())
    f.setPixelSize(px)
    f.setWeight(PESOS.get(peso, QFont.Normal))
    return f


def cor(hex_, alfa=1.0):
    c = QColor(hex_)
    c.setAlphaF(alfa)
    return c


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def vidro(p, r, raio=18, brilho=0.12):
    """Fundo de vidro fosco: branco translúcido + filete de luz."""
    caminho = QPainterPath()
    caminho.addRoundedRect(r, raio, raio)
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0, QColor(255, 255, 255, int(255 * (brilho + 0.06))))
    g.setColorAt(1, QColor(255, 255, 255, int(255 * (brilho - 0.04))))
    p.fillPath(caminho, g)
    p.setPen(QPen(QColor(255, 255, 255, 56), 1))
    p.drawPath(caminho)


# ---------------------------------------------------------------- cards do painel de marca

class CardVendas(QWidget):
    """Vendido hoje: número que sobe, variação e gráfico que se desenha."""
    DADOS = [12, 18, 15, 24, 22, 31, 28, 38, 35, 46, 44, 58, 54, 70]

    def __init__(self, pai):
        super().__init__(pai)
        self.setFixedSize(310, 178)
        self.t0 = 0.0
        self.alvo = 3482.40
        self.exibido = 0.0
        self.pulso = 0.0

    def somar(self, valor):
        self.alvo += valor
        self.pulso = 1.0

    def passo(self, t, dt):
        if self.t0 == 0.0:
            self.t0 = t
        self.exibido += (self.alvo - self.exibido) * min(1.0, dt * 3.2)
        self.pulso = max(0.0, self.pulso - dt * 1.6)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        vidro(p, r, 20)
        p.setPen(QColor(255, 255, 255, 190))
        p.setFont(fonte(13, 600))
        p.drawText(QRectF(22, 18, 180, 20), Qt.AlignLeft | Qt.AlignVCenter, "Vendido hoje")
        # selo de variação
        sel = QRectF(r.right() - 84, 16, 66, 24)
        cam = QPainterPath(); cam.addRoundedRect(sel, 12, 12)
        p.fillPath(cam, QColor(34, 197, 94, 70 + int(60 * self.pulso)))
        p.setPen(QColor("#86EFAC")); p.setFont(fonte(12, 700))
        p.drawText(sel, Qt.AlignCenter, "+12%")
        # valor
        v = f"R$ {self.exibido:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        p.setPen(QColor("white")); p.setFont(fonte(34, 800, True))
        p.drawText(QRectF(22, 44, r.width() - 30, 46), Qt.AlignLeft | Qt.AlignVCenter, v)
        # sparkline que se desenha
        prog = ease((self._t_local()) / 2.2)
        area = QRectF(22, 98, r.width() - 44, 62)
        n = len(self.DADOS)
        mx = max(self.DADOS)
        pts = [QPointF(area.left() + i * area.width() / (n - 1), area.bottom() - self.DADOS[i] / mx * area.height()) for i in range(n)]
        total = prog * (n - 1)
        inteiro = int(total)
        caminho = QPainterPath(pts[0])
        for i in range(1, inteiro + 1):
            caminho.lineTo(pts[i])
        if inteiro < n - 1:
            a, b = pts[inteiro], pts[inteiro + 1]
            f = total - inteiro
            ponta = QPointF(a.x() + (b.x() - a.x()) * f, a.y() + (b.y() - a.y()) * f)
            caminho.lineTo(ponta)
        else:
            ponta = pts[-1]
        fill = QPainterPath(caminho)
        fill.lineTo(ponta.x(), area.bottom()); fill.lineTo(area.left(), area.bottom()); fill.closeSubpath()
        g = QLinearGradient(0, area.top(), 0, area.bottom())
        g.setColorAt(0, QColor(147, 197, 253, 110)); g.setColorAt(1, QColor(147, 197, 253, 0))
        p.fillPath(fill, g)
        p.setPen(QPen(QColor("#BFDBFE"), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(caminho)
        # ponta pulsando
        anel = 6 + 5 * abs(math.sin(self.t0 * 0 + self._tg * 2.2))
        p.setPen(Qt.NoPen); p.setBrush(QColor(191, 219, 254, 70)); p.drawEllipse(ponta, anel, anel)
        p.setBrush(QColor("white")); p.drawEllipse(ponta, 3.6, 3.6)

    _tg = 0.0

    def _t_local(self):
        return max(0.0, self._tg - self.t0)


class CardAvisos(QWidget):
    """Notificações chegando ao vivo: venda, fiado recebido, boleto pago."""
    MSGS = [("#22C55E", "dollar-sign", "Venda #1043 · Pix", "R$ 54,50 · Ana", 54.50),
            ("#60A5FA", "wallet", "Fiado recebido", "Maria Souza · R$ 150,00", 0),
            ("#F59E0B", "check", "Boleto pago", "Energia elétrica · R$ 612,00", 0),
            ("#22C55E", "shopping-cart", "Venda #1044 · Cartão", "R$ 189,90 · Bruna", 189.90),
            ("#A78BFA", "users", "Novo cliente", "João Pedro cadastrado", 0)]
    ALTURA = 68
    PASSO = 78

    def __init__(self, pai, ao_somar):
        super().__init__(pai)
        self.setFixedSize(340, self.PASSO * 3 + 8)
        self.ao_somar = ao_somar
        self.itens = []          # mais novo primeiro: (msg, nasc)
        self.prox = 0
        self.ultimo = -99.0
        self.t = 0.0

    def passo(self, t, dt):
        self.t = t
        if t - self.ultimo > 3.3 and t > 1.4:
            self.ultimo = t
            msg = self.MSGS[self.prox % len(self.MSGS)]
            self.prox += 1
            self.itens.insert(0, (msg, t))
            self.itens = self.itens[:4]
            if msg[4]:
                self.ao_somar(msg[4])
        self.update()

    def paintEvent(self, _):
        if not self.itens:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        e = ease((self.t - self.itens[0][1]) / 0.55)
        for i, (msg, nasc) in enumerate(self.itens):
            y = (i - 1) * self.PASSO + self.PASSO * e if i > 0 else -26 * (1 - e)
            alfa = e if i == 0 else (1.0 - (e if i == 3 else 0.0)) * (1.0 - 0.18 * i)
            p.setOpacity(max(0.0, alfa))
            r = QRectF(0, y + 4, self.width(), self.ALTURA)
            vidro(p, r, 18, 0.13)
            p.setPen(Qt.NoPen)
            p.setBrush(cor(msg[0], 0.22)); p.drawEllipse(QRectF(14, y + 4 + (self.ALTURA - 40) / 2, 40, 40))
            p.drawPixmap(34 - 9, int(y + 4 + self.ALTURA / 2 - 9), icone(msg[1], msg[0], 18).pixmap(18, 18))
            p.setPen(QColor("white")); p.setFont(fonte(14, 700))
            p.drawText(QRectF(66, y + 14, 220, 22), Qt.AlignLeft | Qt.AlignVCenter, msg[2])
            p.setPen(QColor(255, 255, 255, 165)); p.setFont(fonte(12, 400))
            p.drawText(QRectF(66, y + 36, 240, 20), Qt.AlignLeft | Qt.AlignVCenter, msg[3])
            seg = int(self.t - nasc)
            p.setFont(fonte(11, 500)); p.setPen(QColor(255, 255, 255, 120))
            p.drawText(QRectF(self.width() - 70, y + 14, 56, 20), Qt.AlignRight | Qt.AlignVCenter, "agora" if seg < 6 else f"há {seg}s")
        p.setOpacity(1.0)


class CardPagamentos(QWidget):
    LINHAS = [("Pix", 46, "#60A5FA"), ("Cartão", 31, "#A78BFA"), ("Dinheiro", 17, "#34D399"), ("Fiado", 6, "#FBBF24")]

    def __init__(self, pai):
        super().__init__(pai)
        self.setFixedSize(272, 176)
        self.t = 0.0

    def passo(self, t, dt):
        self.t = t
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        vidro(p, r, 20)
        p.setPen(QColor(255, 255, 255, 200)); p.setFont(fonte(13, 600))
        p.drawText(QRectF(20, 16, 220, 20), Qt.AlignLeft | Qt.AlignVCenter, "Formas de pagamento")
        for i, (nome, pct, c) in enumerate(self.LINHAS):
            y = 50 + i * 30
            prog = ease((self.t - 0.9 - i * 0.18) / 1.1)
            p.setPen(QColor(255, 255, 255, 190)); p.setFont(fonte(12, 500))
            p.drawText(QRectF(20, y, 62, 20), Qt.AlignLeft | Qt.AlignVCenter, nome)
            trilho = QRectF(86, y + 5, 120, 10)
            cam = QPainterPath(); cam.addRoundedRect(trilho, 5, 5); p.fillPath(cam, QColor(255, 255, 255, 30))
            larg = trilho.width() * pct / 50 * prog
            if larg > 1:
                barra = QRectF(trilho.left(), trilho.top(), min(larg, trilho.width()), trilho.height())
                cb = QPainterPath(); cb.addRoundedRect(barra, 5, 5)
                g = QLinearGradient(barra.topLeft(), barra.topRight()); g.setColorAt(0, cor(c, 0.7)); g.setColorAt(1, cor(c, 1.0))
                p.fillPath(cb, g)
                # brilho que passeia
                x = barra.left() + ((self.t * 0.5 + i * 0.2) % 1.4) / 1.4 * barra.width()
                gl = QLinearGradient(x - 16, 0, x + 16, 0)
                gl.setColorAt(0, QColor(255, 255, 255, 0)); gl.setColorAt(0.5, QColor(255, 255, 255, 90)); gl.setColorAt(1, QColor(255, 255, 255, 0))
                p.save(); p.setClipPath(cb); p.fillRect(barra, gl); p.restore()
            p.setPen(QColor("white")); p.setFont(fonte(12, 700))
            p.drawText(QRectF(212, y, 44, 20), Qt.AlignRight | Qt.AlignVCenter, f"{int(pct * prog)}%")


# ---------------------------------------------------------------- fundo vivo

class Fundo(QWidget):
    frase1, frase2 = "Sua loja organizada,", "do caixa ao fiado."
    sub = "Vendas, estoque, clientes e contas num lugar só."

    def criar_cards(self):
        self.card_vendas = CardVendas(self)
        self.card_pag = CardPagamentos(self)
        self.card_avisos = CardAvisos(self, self.card_vendas.somar)
        self.itens = [(self.card_vendas, 16, 0.0), (self.card_avisos, 26, 1.7), (self.card_pag, 10, 3.1)]

    def posicoes(self, w, h):
        return {self.card_vendas: QPointF(w * 0.09, h * 0.20),
                self.card_avisos: QPointF(w - 340 - w * 0.07, h * 0.36),
                self.card_pag: QPointF(w * 0.14, h * 0.50)}

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.mouse = None
        self.par = QPointF(0, 0)
        self.relogio = QElapsedTimer(); self.relogio.start()
        self.anterior = 0.0
        self.criar_cards()
        self.base = {}
        self.timer = QTimer(self); self.timer.setInterval(16); self.timer.timeout.connect(self.tick)
        # "Mostrar animacoes" desligado no Windows: fica parado num quadro so
        if not movimento_reduzido():
            self.timer.start()

    def parar_animacao(self):
        self.timer.stop()

    def resizeEvent(self, e):
        w, h = self.width(), self.height()
        self.base = self.posicoes(w, h)
        # janela estreita: os cards (decoracao) se sobreporiam, entao somem
        for c, _f, _p in self.itens:
            c.setVisible(w >= 720)
        if not self.timer.isActive():
            self.tick()
        super().resizeEvent(e)

    def mouseMoveEvent(self, e):
        self.mouse = e.position()

    def leaveEvent(self, e):
        self.mouse = None

    def tick(self):
        t = self.relogio.elapsed() / 1000.0
        dt = max(0.001, t - self.anterior); self.anterior = t
        w, h = self.width(), self.height()
        alvo = QPointF(0, 0)
        if self.mouse is not None and w and h:
            alvo = QPointF((self.mouse.x() / w - 0.5) * 2, (self.mouse.y() / h - 0.5) * 2)
        self.par += (alvo - self.par) * min(1.0, dt * 3.0)
        for c, fator, fase in self.itens:
            b = self.base.get(c)
            if b is None:
                continue
            c._tg = t
            flut = math.sin(t * 0.9 + fase) * 6
            c.move(int(b.x() - self.par.x() * fator), int(b.y() - self.par.y() * fator + flut))
            c.passo(t, dt)
        self.t = t
        self.update()

    t = 0.0

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0, QColor(T.SIDEBAR)); g.setColorAt(1, QColor(T.SIDEBAR).darker(135))
        p.fillRect(self.rect(), g)
        # auroras: três manchas que passeiam devagar
        for fase, (rr, gg, bb), raio, sx, sy in ((0.0, (59, 130, 246), 0.62, 0.21, 0.17), (2.1, (34, 211, 238), 0.46, 0.17, 0.23), (4.2, (139, 92, 246), 0.55, 0.13, 0.19)):
            cx = w * (0.5 + 0.38 * math.sin(self.t * sx + fase))
            cy = h * (0.5 + 0.36 * math.cos(self.t * sy + fase * 1.3))
            rd = max(w, h) * raio
            rg = QRadialGradient(cx, cy, rd)
            rg.setColorAt(0, QColor(rr, gg, bb, 120)); rg.setColorAt(1, QColor(rr, gg, bb, 0))
            p.fillRect(self.rect(), rg)
        # grade de pontos com holofote no mouse
        mx = self.mouse.x() if self.mouse is not None else -999
        my = self.mouse.y() if self.mouse is not None else -999
        p.setPen(Qt.NoPen)
        esp = 26
        for x in range(esp // 2, w, esp):
            for y in range(esp // 2, h, esp):
                d = math.hypot(x - mx, y - my)
                prox = max(0.0, 1 - d / 170) ** 2
                p.setBrush(QColor(255, 255, 255, int(26 + 190 * prox)))
                rr = 1.1 + 1.6 * prox
                p.drawEllipse(QPointF(x, y), rr, rr)
        # marca
        p.setBrush(QColor(255, 255, 255, 40)); p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.drawRoundedRect(QRectF(44, 38, 42, 42), 13, 13)
        p.setPen(QColor("white")); p.setFont(fonte(21, 800, True))
        p.drawText(QRectF(44, 38, 42, 42), Qt.AlignCenter, "V")
        p.setFont(fonte(21, 700, True))
        p.drawText(QRectF(98, 38, 240, 42), Qt.AlignLeft | Qt.AlignVCenter, "Vertex ERP")
        # frase
        p.setFont(fonte(34, 800, True)); p.setPen(QColor("white"))
        p.drawText(QRectF(44, h - 168, w - 88, 44), Qt.AlignLeft | Qt.AlignVCenter, self.frase1)
        p.drawText(QRectF(44, h - 126, w - 88, 44), Qt.AlignLeft | Qt.AlignVCenter, self.frase2)
        p.setFont(fonte(14, 400)); p.setPen(QColor(255, 255, 255, 170))
        p.drawText(QRectF(44, h - 76, w - 88, 24), Qt.AlignLeft | Qt.AlignVCenter, self.sub)


# ---------------------------------------------------------------- botão e formulário

class BotaoEntrar(QPushButton):
    def __init__(self):
        super().__init__("Entrar")
        self.rotulo = "Entrar"
        self.rotulo_carregando = "Entrando…"
        self.setFixedHeight(52)
        self.setCursor(Qt.PointingHandCursor)
        self.estado = "idle"   # idle | carregando | ok
        self.texto_ok = "Bem-vindo!"
        self.fase = 0.0
        self.sobre = False
        self.timer = QTimer(self); self.timer.setInterval(16); self.timer.timeout.connect(self._gira)

    def definir(self, estado):
        self.estado = estado
        self.setEnabled(estado == "idle")
        (self.timer.start if estado == "carregando" else self.timer.stop)()
        self.update()

    def _gira(self):
        self.fase = (self.fase + 7) % 360
        self.update()

    def enterEvent(self, e):
        self.sobre = True; self.update()

    def leaveEvent(self, e):
        self.sobre = False; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        base = T.SUCESSO if self.estado == "ok" else (T.PRIMARIA_HOVER if self.sobre else T.PRIMARIA)
        cam = QPainterPath(); cam.addRoundedRect(r, T.RADIUS_MD + 2, T.RADIUS_MD + 2)
        g = QLinearGradient(r.topLeft(), r.bottomLeft()); g.setColorAt(0, QColor(base).lighter(112)); g.setColorAt(1, QColor(base))
        p.fillPath(cam, g)
        p.setPen(QColor("white")); p.setFont(fonte(16, 700))
        if self.estado == "carregando":
            p.setPen(QPen(QColor(255, 255, 255, 230), 3, Qt.SolidLine, Qt.RoundCap))
            c = QPointF(r.center().x() - 62, r.center().y())
            p.drawArc(QRectF(c.x() - 10, c.y() - 10, 20, 20), int(-self.fase * 16), 270 * 16)
            p.setPen(QColor("white"))
            p.drawText(QRectF(r.center().x() - 36, 0, 150, r.height()), Qt.AlignLeft | Qt.AlignVCenter, self.rotulo_carregando)
        elif self.estado == "ok":
            p.drawPixmap(int(r.center().x() - 74), int(r.center().y() - 11), icone("check", "#FFFFFF", 22).pixmap(22, 22))
            p.drawText(QRectF(r.center().x() - 46, 0, 160, r.height()), Qt.AlignLeft | Qt.AlignVCenter, self.texto_ok)
        else:
            larg = p.fontMetrics().horizontalAdvance(self.rotulo)
            p.drawText(r.adjusted(0, 0, -26, 0), Qt.AlignCenter, self.rotulo)
            p.setPen(QPen(QColor("white"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            ax = r.center().x() - 13 + larg / 2 + 22 + (4 if self.sobre else 0); ay = r.center().y()
            p.drawLine(QPointF(ax - 6, ay), QPointF(ax + 6, ay)); p.drawLine(QPointF(ax + 1, ay - 5), QPointF(ax + 6, ay)); p.drawLine(QPointF(ax + 1, ay + 5), QPointF(ax + 6, ay))


class Onda(QWidget):
    """Revelação ao entrar: um círculo azul cresce do botão e cobre a tela."""

    def __init__(self, pai):
        super().__init__(pai)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.centro = QPointF(0, 0); self.p = 0.0; self.nome = ""; self.hide()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        diag = math.hypot(self.width(), self.height()) * 1.05
        raio = diag * ease(self.p / 0.62)
        g = QRadialGradient(self.centro, max(raio, 1)); g.setColorAt(0, QColor(T.PRIMARIA).lighter(115)); g.setColorAt(1, QColor(T.PRIMARIA))
        p.setPen(Qt.NoPen); p.setBrush(g); p.drawEllipse(self.centro, raio, raio)
        a = ease((self.p - 0.5) / 0.3)
        p.setOpacity(a)
        p.setPen(QColor("white")); p.setFont(fonte(44, 800, True))
        p.drawText(QRectF(0, self.height() / 2 - 70, self.width(), 70), Qt.AlignCenter, f"Bem-vindo, {self.nome}")
        p.setFont(fonte(17, 400)); p.setPen(QColor(255, 255, 255, 200))
        p.drawText(QRectF(0, self.height() / 2 + 4, self.width(), 30), Qt.AlignCenter, "Abrindo a sua loja…")



# ---------------------------------------------------------------- primeiro acesso

D = {}   # o que a pessoa já preencheu (alimenta os cards de prévia)
PASSOS_NOMES = ["Sua conta", "Segurança", "Sua loja", "Contato", "Recebimento"]


def valida_email(t):
    return None if "@" in t and "." in t.split("@")[-1] else "Esse e-mail parece incompleto (ex.: voce@loja.com)."


def forca(txt):
    n = (len(txt) >= 6) + (len(txt) >= 9) + (any(c.isdigit() for c in txt) and any(c.isalpha() for c in txt)) + (any(not c.isalnum() for c in txt) or (any(c.isupper() for c in txt) and any(c.islower() for c in txt)))
    return n, ["Muito curta", "Fraca", "Razoável", "Boa", "Forte"][n if txt else 0] if txt else ""


# ----------------------------------------------------------------- cards de prévia (painel esquerdo)

class CardPassos(QWidget):
    def __init__(self, pai):
        super().__init__(pai)
        self.setFixedSize(272, 352)
        self.atual = 0
        self.pos = 0.0
        self.t = 0.0

    def passo(self, t, dt):
        self.t = t
        self.pos += (self.atual - self.pos) * min(1.0, dt * 5)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        vidro(p, r, 20)
        pronto = self.atual >= len(PASSOS_NOMES)
        p.setPen(QColor(255, 255, 255, 210)); p.setFont(fonte(13, 600))
        p.drawText(QRectF(22, 16, 230, 22), Qt.AlignLeft | Qt.AlignVCenter, "Tudo pronto!" if pronto else "Primeiros passos")
        nomes = PASSOS_NOMES + ["Pronto!"]
        for i, nome in enumerate(nomes):
            cy = 66 + i * 46
            cx = 36
            feito = i < self.pos - 0.35 or pronto
            foco = max(0.0, 1 - abs(i - self.pos)) if not pronto else 0.0
            if i < len(nomes) - 1:
                p.setPen(QPen(QColor(34, 197, 94, 190) if i < self.pos - 0.6 or pronto else QColor(255, 255, 255, 40), 2))
                p.drawLine(QPointF(cx, cy + 16), QPointF(cx, cy + 30))
            p.setPen(Qt.NoPen)
            if feito:
                p.setBrush(QColor(34, 197, 94, 235)); p.drawEllipse(QPointF(cx, cy), 14, 14)
                p.drawPixmap(int(cx - 8), int(cy - 8), icone("check", "#FFFFFF", 16).pixmap(16, 16))
            else:
                p.setBrush(QColor(255, 255, 255, int(24 + 40 * foco))); p.setPen(QPen(QColor(255, 255, 255, int(70 + 170 * foco)), 1.6))
                p.drawEllipse(QPointF(cx, cy), 14, 14)
                if foco > 0.5:
                    anel = 14 + 4 + 3 * abs(math.sin(self.t * 2.4))
                    p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(147, 197, 253, 90), 2)); p.drawEllipse(QPointF(cx, cy), anel, anel)
                p.setPen(QColor(255, 255, 255, int(110 + 140 * foco))); p.setFont(fonte(12, 700))
                p.drawText(QRectF(cx - 14, cy - 14, 28, 28), Qt.AlignCenter, str(i + 1))
            alfa = 255 if (foco > 0.5) else (205 if feito else 115)
            p.setPen(QColor(255, 255, 255, alfa)); p.setFont(fonte(14, 700 if foco > 0.5 else 500))
            p.drawText(QRectF(62, cy - 12, 190, 24), Qt.AlignLeft | Qt.AlignVCenter, nome)


class CardLoja(QWidget):
    def __init__(self, pai):
        super().__init__(pai)
        self.setFixedSize(340, 212)
        self.visto = {}
        self.flash = {}
        self.t = 0.0

    def passo(self, t, dt):
        self.t = t
        for k in ("loja", "cnpj", "tel", "end"):
            v = D.get(k, "")
            if v != self.visto.get(k):
                self.visto[k] = v; self.flash[k] = 1.0
            self.flash[k] = max(0.0, self.flash.get(k, 0.0) - dt * 1.5)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        vidro(p, r, 22)
        p.setPen(QColor(255, 255, 255, 150)); p.setFont(fonte(11, 700))
        p.drawText(QRectF(22, 14, 200, 18), Qt.AlignLeft | Qt.AlignVCenter, "SUA LOJA NO VERTEX")
        # logo ou monograma
        av = QRectF(22, 42, 62, 62)
        cam = QPainterPath(); cam.addRoundedRect(av, 16, 16)
        logo = D.get("logo")
        if logo is not None and not logo.isNull():
            p.save(); p.setClipPath(cam); p.drawPixmap(av.toRect(), logo.scaled(62, 62, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)); p.restore()
        else:
            g = QLinearGradient(av.topLeft(), av.bottomRight()); g.setColorAt(0, QColor("#60A5FA")); g.setColorAt(1, QColor("#8B5CF6"))
            p.fillPath(cam, g)
            ini = "".join(w[0] for w in (D.get("loja") or "?").split()[:2]).upper() or "?"
            p.setPen(QColor("white")); p.setFont(fonte(24, 800, True)); p.drawText(av, Qt.AlignCenter, ini)
        nome = D.get("loja") or "Nome da sua loja"
        vazio = not D.get("loja")
        p.setPen(QColor(255, 255, 255, 120 if vazio else 255)); p.setFont(fonte(20, 800, True))
        p.drawText(QRectF(98, 46, 230, 30), Qt.AlignLeft | Qt.AlignVCenter, p.fontMetrics().elidedText(nome, Qt.ElideRight, 226))
        p.setFont(fonte(12, 500)); p.setPen(QColor(255, 255, 255, 140))
        p.drawText(QRectF(98, 76, 230, 22), Qt.AlignLeft | Qt.AlignVCenter, "Loja principal  ·  Matriz")
        for i, (chave, rot, ph) in enumerate((("cnpj", "CNPJ/CPF", "000.000.000/0001-00"), ("tel", "WhatsApp", "(00) 00000-0000"), ("end", "Endereço", "Rua, número, cidade"))):
            y = 120 + i * 28
            f = self.flash.get(chave, 0.0)
            if f > 0:
                hl = QPainterPath(); hl.addRoundedRect(QRectF(14, y - 3, r.width() - 26, 26), 8, 8)
                p.fillPath(hl, QColor(147, 197, 253, int(70 * f)))
            p.setPen(QColor(255, 255, 255, 110)); p.setFont(fonte(11, 600))
            p.drawText(QRectF(24, y, 78, 20), Qt.AlignLeft | Qt.AlignVCenter, rot)
            v = D.get(chave)
            p.setPen(QColor(255, 255, 255, 235 if v else 80)); p.setFont(fonte(13, 600 if v else 400))
            p.drawText(QRectF(104, y, 224, 20), Qt.AlignLeft | Qt.AlignVCenter, p.fontMetrics().elidedText(v or ph, Qt.ElideRight, 220))


class CardCupom(QWidget):
    def __init__(self, pai):
        super().__init__(pai)
        self.setFixedSize(236, 300)
        random.seed(7)
        self.qr = [[random.random() > 0.5 for _ in range(9)] for _ in range(9)]

    def passo(self, t, dt):
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height() - 6
        papel = QPainterPath(); papel.moveTo(2, 2); papel.lineTo(w - 2, 2); papel.lineTo(w - 2, h)
        x = w - 2
        while x > 2:
            papel.lineTo(x - 7, h + 6); papel.lineTo(x - 14, h); x -= 14
        papel.lineTo(2, h); papel.closeSubpath()
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 40)); p.drawPath(papel.translated(0, 3))
        p.setBrush(QColor(255, 255, 255, 244)); p.drawPath(papel)
        escuro = QColor("#0F172A")
        nome = (D.get("loja") or "SUA LOJA").upper()
        p.setPen(escuro); p.setFont(fonte(14, 800, True))
        p.drawText(QRectF(10, 14, w - 20, 22), Qt.AlignCenter, p.fontMetrics().elidedText(nome, Qt.ElideRight, w - 24))
        p.setFont(fonte(10, 500)); p.setPen(QColor("#64748B"))
        p.drawText(QRectF(10, 36, w - 20, 16), Qt.AlignCenter, D.get("cnpj") or "CUPOM NÃO FISCAL")
        p.drawText(QRectF(10, 51, w - 20, 16), Qt.AlignCenter, p.fontMetrics().elidedText(D.get("tel") or "", Qt.ElideRight, w - 24))
        p.setPen(QPen(QColor("#CBD5E1"), 1, Qt.DashLine)); p.drawLine(14, 76, w - 14, 76)
        itens = (("1x Caderno 10 mat.", "18,90"), ("2x Caneta azul", "7,80"), ("1x Garrafa 500ml", "49,90"))
        p.setFont(fonte(11, 500))
        for i, (a, b) in enumerate(itens):
            p.setPen(escuro); p.drawText(QRectF(14, 84 + i * 20, 140, 18), Qt.AlignLeft | Qt.AlignVCenter, a)
            p.drawText(QRectF(w - 70, 84 + i * 20, 56, 18), Qt.AlignRight | Qt.AlignVCenter, b)
        p.setPen(QPen(QColor("#CBD5E1"), 1, Qt.DashLine)); p.drawLine(14, 148, w - 14, 148)
        p.setPen(escuro); p.setFont(fonte(14, 800)); p.drawText(QRectF(14, 154, 100, 24), Qt.AlignLeft | Qt.AlignVCenter, "TOTAL")
        p.drawText(QRectF(w - 110, 154, 96, 24), Qt.AlignRight | Qt.AlignVCenter, "R$ 76,60")
        pix = D.get("pix")
        p.setFont(fonte(10, 600)); p.setPen(QColor("#64748B"))
        p.drawText(QRectF(14, 184, w - 28, 16), Qt.AlignCenter, "Pague com Pix" if pix else "Pix: informe a chave para o QR Code")
        # QR de exemplo
        lado = 74; x0 = (w - lado) / 2; y0 = 206
        for yy in range(9):
            for xx in range(9):
                if pix and (self.qr[yy][xx] or (xx < 3 and yy < 3) or (xx > 5 and yy < 3) or (xx < 3 and yy > 5)):
                    p.fillRect(QRectF(x0 + xx * lado / 9, y0 + yy * lado / 9, lado / 9 + 0.5, lado / 9 + 0.5), escuro)
                elif not pix:
                    p.fillRect(QRectF(x0 + xx * lado / 9, y0 + yy * lado / 9, lado / 9 - 1, lado / 9 - 1), QColor("#E2E8F0"))


class FundoBV(Fundo):
    frase1, frase2 = "Bem-vindo ao Vertex.", "Vamos montar a sua loja."
    sub = "Em poucos minutos você está vendendo."

    def criar_cards(self):
        self.passos = CardPassos(self)
        self.loja = CardLoja(self)
        self.cupom = CardCupom(self)
        self.itens = [(self.passos, 12, 0.0), (self.loja, 22, 1.7), (self.cupom, 30, 3.1)]

    def posicoes(self, w, h):
        return {self.passos: QPointF(w * 0.07, h * 0.15),
                self.loja: QPointF(w - 340 - w * 0.07, h * 0.18),
                self.cupom: QPointF(w - 236 - w * 0.13, h * 0.18 + 226)}


# ----------------------------------------------------------------- confete

class Confete(QWidget):
    CORES = ["#60A5FA", "#34D399", "#FBBF24", "#F472B6", "#A78BFA", "#FFFFFF"]

    def __init__(self, pai):
        super().__init__(pai)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.ps = []
        self.t = QTimer(self); self.t.setInterval(16); self.t.timeout.connect(self.passo)
        self.hide()

    def disparar(self, x, y):
        self.setGeometry(self.parent().rect()); self.show(); self.raise_()
        for _ in range(170):
            ang = random.uniform(-math.pi * 0.95, -math.pi * 0.05)
            v = random.uniform(380, 980)
            self.ps.append([x, y, math.cos(ang) * v, math.sin(ang) * v, random.uniform(0, 6.28), random.uniform(-9, 9),
                            random.choice(self.CORES), random.uniform(6, 12), random.uniform(0, 0.25), 0.0])
        self.t.start()

    def passo(self):
        dt = 0.016
        vivos = []
        for q in self.ps:
            q[9] += dt
            if q[9] < q[8]:
                vivos.append(q); continue
            q[3] += 980 * dt; q[2] *= 0.992; q[0] += q[2] * dt; q[1] += q[3] * dt; q[4] += q[5] * dt
            if q[1] < self.height() + 40 and q[9] < 4.2:
                vivos.append(q)
        self.ps = vivos
        self.update()
        if not self.ps:
            self.t.stop(); self.hide()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        for x, y, vx, vy, rot, vr, c, tam, atraso, vida in self.ps:
            if vida < atraso:
                continue
            p.save(); p.translate(x, y); p.rotate(math.degrees(rot))
            p.setBrush(QColor(c)); p.drawRoundedRect(QRectF(-tam / 2, -tam / 3, tam, tam * 0.6), 2, 2)
            p.restore()

