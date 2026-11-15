from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from services import api
from services.caixa_service import historico_caixa
from services.worker import rodar_em_thread

from design import tokens
from design.icons import icone_pixmap
from design.privacidade import privacidade
from design.widgets import (
    Avatar, Badge, BotaoSucesso, DialogoPadrao, campo_rotulado, titulo_secao,
)
from utils.formatacao import formatar_moeda, ler_moeda

VALORES_RAPIDOS = [50, 100, 150, 200, 300, 500]


def troco_que_ficou(sessao):
    """Quanto ficou na gaveta no fechamento daquela sessao: o que estava
    disponivel (contado, ou o esperado se nao contou) menos o que foi pro
    cofre/banco e a retirada dos socios -- mesma conta do fechamento no
    backend (CaixaService.fechar). None se a sessao ainda esta aberta."""

    if sessao.get("status") == "ABERTO":
        return None

    contado = sessao.get("valor_contado")
    disponivel = float(contado if contado is not None else sessao.get("saldo_final") or 0)

    return round(
        disponivel
        - float(sessao.get("valor_guardado") or 0)
        - float(sessao.get("valor_retirado") or 0),
        2,
    )


def selo_sessao(sessao):
    """(texto, variante do Badge) -- Conferido / Faltou / Sobrou / Aberto."""

    if sessao.get("status") == "ABERTO":
        return "Aberto", "info"

    contado = sessao.get("valor_contado")
    if contado is None:
        return "Fechado", "neutro"

    diferenca = round(float(contado) - float(sessao.get("saldo_final") or 0), 2)

    if abs(diferenca) < 0.01:
        return "Conferido", "sucesso"
    if diferenca < 0:
        return f"Faltou {formatar_moeda(-diferenca)}", "erro"
    return f"Sobrou {formatar_moeda(diferenca)}", "alerta"


def quando(texto):
    """'Hoje' / 'Ontem' / '13/11' a partir da data da abertura."""

    try:
        dia = datetime.fromisoformat(str(texto).replace("T", " ")[:19]).date()
    except ValueError:
        return str(texto or "")[:10]

    dias = (datetime.now().date() - dia).days
    if dias == 0:
        return "Hoje"
    if dias == 1:
        return "Ontem"
    return dia.strftime("%d/%m")


class AbrirCaixaWindow(DialogoPadrao):

    def __init__(self):

        # Vendedor nao ve o historico (tem o valor de cada fechamento)
        ve_historico = api.usuario_tem_permissao("financeiro.ver")

        super().__init__(
            "Abrir Caixa", "Informe o troco inicial para liberar o caixa",
            "wallet", tokens.SECUNDARIA_HOVER, tokens.SUCESSO_CLARO,
            largura=DialogoPadrao.GRANDE if ve_historico else DialogoPadrao.PEQUENO,
            cor_fim=tokens.SECUNDARIA_ESCURA,
        )

        self._chips = {}

        # ======================
        # VALOR + ATALHOS + SUGESTAO
        # ======================

        self.valor = QLineEdit()
        self.valor.setPlaceholderText("R$ 0,00")
        self.valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.valor.setMinimumHeight(72)
        self.valor.setStyleSheet(f"""
            QLineEdit {{
                font-size:36px; font-weight:800; color:{tokens.TEXTO};
                border:2px solid {tokens.BORDA_CAMPO}; border-radius:{tokens.RADIUS_MD}px;
                padding:0 20px; background:{tokens.CARD};
            }}
            QLineEdit:focus {{ border-color:{tokens.SUCESSO}; }}
        """)
        self.valor.textChanged.connect(self._pintar_chips)

        esquerda = QVBoxLayout()
        esquerda.setSpacing(10)
        esquerda.addWidget(campo_rotulado("Valor inicial (troco)", self.valor))
        esquerda.addLayout(self._linha_valores())

        # aparece quando o historico chega e ha' uma sessao fechada pra copiar
        self.cartao_sugestao = self._construir_sugestao()
        self.cartao_sugestao.hide()
        esquerda.addSpacing(4)
        esquerda.addWidget(self.cartao_sugestao)
        esquerda.addStretch()

        corpo = QHBoxLayout()
        corpo.setSpacing(28)
        corpo.addLayout(esquerda, 1)

        # ======================
        # HISTÓRICO DE SESSÕES
        # ======================

        if ve_historico:
            painel = QFrame()
            painel.setObjectName("painelSessoes")
            painel.setFixedWidth(320)
            painel.setStyleSheet(
                f"QFrame#painelSessoes {{ background:{tokens.FUNDO}; border:none; "
                f"border-radius:{tokens.RADIUS_LG}px; }}"
            )
            layout_painel = QVBoxLayout(painel)
            layout_painel.setContentsMargins(18, 16, 18, 16)
            layout_painel.setSpacing(8)
            layout_painel.addWidget(titulo_secao("Últimas sessões"))

            self.historico_layout = QVBoxLayout()
            self.historico_layout.setSpacing(8)
            layout_painel.addLayout(self.historico_layout)
            layout_painel.addStretch()

            corpo.addWidget(painel)
            self.carregar_historico()

        self.corpo.addLayout(corpo)

        self.bt_abrir = BotaoSucesso("Abrir Caixa", icone_nome="check")
        self.bt_abrir.setAutoDefault(False)
        self.bt_abrir.clicked.connect(self.confirmar)
        self.bt_cancelar = self.definir_botoes(self.bt_abrir)

        self.ajustar_altura()
        self.valor.setFocus()

    # ======================================

    def _linha_valores(self):

        linha = QHBoxLayout()
        linha.setSpacing(8)

        for valor in VALORES_RAPIDOS:

            bt = QPushButton(f"R$ {valor}")
            bt.setCursor(Qt.PointingHandCursor)
            bt.setFixedHeight(40)
            bt.setAutoDefault(False)
            bt.setFocusPolicy(Qt.NoFocus)
            bt.clicked.connect(lambda checked=False, v=valor: self.definir_valor(v))

            self._chips[valor] = bt
            linha.addWidget(bt, 1)

        self._pintar_chips()

        return linha

    def _pintar_chips(self, *_):

        atual = self.saldo

        for valor, bt in self._chips.items():
            sel = abs(atual - valor) < 0.005
            bt.setStyleSheet(f"""
                QPushButton {{
                    border:{'2px' if sel else '1px'} solid {tokens.SUCESSO if sel else tokens.BORDA_FORTE};
                    border-radius:{tokens.RADIUS_SM + 2}px;
                    background:{tokens.SUCESSO_CLARO if sel else tokens.CARD};
                    color:{tokens.SECUNDARIA_HOVER if sel else tokens.TEXTO};
                    font-weight:600; font-size:{tokens.TAMANHO_SM}px;
                }}
                QPushButton:hover {{ border-color:{tokens.SUCESSO}; }}
            """)

    def _construir_sugestao(self):

        cartao = QFrame()
        cartao.setObjectName("sugestaoTroco")
        cartao.setStyleSheet(f"""
            QFrame#sugestaoTroco {{
                background:{tokens.SUCESSO_CLARO}; border:1px solid {tokens.SUCESSO};
                border-radius:{tokens.RADIUS_MD}px;
            }}
        """)

        layout = QHBoxLayout(cartao)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(12)

        icone = QLabel()
        icone.setFixedSize(40, 40)
        icone.setAlignment(Qt.AlignCenter)
        icone.setPixmap(icone_pixmap("refresh-cw", cor=tokens.SUCESSO, tamanho=18))
        icone.setStyleSheet(f"background:{tokens.CARD}; border:none; border-radius:20px;")
        layout.addWidget(icone)

        coluna = QVBoxLayout()
        coluna.setSpacing(0)
        titulo = QLabel("Mesmo troco do último fechamento")
        titulo.setStyleSheet(
            f"background:transparent; border:none; color:{tokens.SECUNDARIA_HOVER}; "
            f"font-size:{tokens.TAMANHO_BASE}px; font-weight:700;"
        )
        self.lbl_sugestao = QLabel()
        self.lbl_sugestao.setStyleSheet(
            f"background:transparent; border:none; color:{tokens.SECUNDARIA_HOVER}; "
            f"font-size:{tokens.TAMANHO_XS}px;"
        )
        coluna.addWidget(titulo)
        coluna.addWidget(self.lbl_sugestao)
        layout.addLayout(coluna, 1)

        self.bt_usar_sugestao = BotaoSucesso("Usar")
        self.bt_usar_sugestao.setAutoDefault(False)
        self.bt_usar_sugestao.setMinimumWidth(70)
        self.bt_usar_sugestao.setFixedHeight(34)
        layout.addWidget(self.bt_usar_sugestao)

        return cartao

    def definir_valor(self, valor):
        self.valor.setText(f"{valor:.2f}")

    def carregar_historico(self):

        # so' essa secao do dialogo depende de rede -- o resto (campo
        # de valor, atalhos, rodape) ja pinta na hora; sem isso, o
        # dialogo inteiro demorava pra aparecer esperando o historico
        rodar_em_thread(
            self,
            historico_caixa,
            ao_sucesso=self._ao_historico_sucesso,
            ao_erro=self._ao_historico_erro,
        )

    def _limpar_historico(self):

        while self.historico_layout.count():
            item = self.historico_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def _ao_historico_erro(self, erro):

        self._limpar_historico()

        vazio = QLabel(f"Não foi possível carregar o histórico.\n{erro}")
        vazio.setWordWrap(True)
        vazio.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        self.historico_layout.addWidget(vazio)

    def _ao_historico_sucesso(self, sessoes):

        self._limpar_historico()

        if not sessoes:
            vazio = QLabel("Nenhuma sessão registrada ainda.")
            vazio.setStyleSheet(f"""
                background:transparent; font-size:{tokens.TAMANHO_SM}px;
                color:{tokens.TEXTO_TERCIARIO};
            """)
            self.historico_layout.addWidget(vazio)
            return

        for sessao in sessoes[:3]:
            self.historico_layout.addWidget(self._cartao_sessao(sessao))

        # sugestao: o troco que ficou na ultima sessao ja fechada
        for sessao in sessoes:
            ficou = troco_que_ficou(sessao)
            if ficou is not None and ficou > 0:
                privacidade.definir_texto(
                    self.lbl_sugestao, f"Ficou {formatar_moeda(ficou)} na gaveta"
                )
                self.bt_usar_sugestao.clicked.connect(
                    lambda checked=False, v=ficou: self.definir_valor(v)
                )
                self.cartao_sugestao.show()
                break

        # adiado: as linhas recém-adicionadas só aparecem (e contam na
        # medida) no próximo ciclo de eventos
        QTimer.singleShot(0, self._ajustar_se_vivo)

    def _ajustar_se_vivo(self):

        # o dialogo pode ter sido fechado (e destruido) antes do ciclo de eventos
        try:
            self.ajustar_altura()
        except RuntimeError:
            pass

    def _cartao_sessao(self, sessao):

        nome = sessao.get("usuario_nome") or "—"

        cartao = QFrame()
        cartao.setObjectName("cartaoSessao")
        cartao.setStyleSheet(f"""
            QFrame#cartaoSessao {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_MD}px;
            }}
        """)

        layout = QHBoxLayout(cartao)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        layout.addWidget(Avatar(nome, 34), 0, Qt.AlignTop)

        coluna = QVBoxLayout()
        coluna.setSpacing(0)

        quem = QLabel(f"{nome} · {quando(sessao.get('data_abertura'))}")
        quem.setStyleSheet(
            f"background:transparent; border:none; color:{tokens.TEXTO}; "
            f"font-size:{tokens.TAMANHO_SM}px; font-weight:700;"
        )
        abriu = QLabel()
        abriu.setStyleSheet(
            f"background:transparent; border:none; color:{tokens.TEXTO_TERCIARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px;"
        )
        privacidade.definir_texto(
            abriu, f"Abriu com {formatar_moeda(float(sessao.get('saldo_inicial') or 0))}"
        )

        texto, variante = selo_sessao(sessao)
        selo = Badge(texto, variante)
        privacidade.definir_texto(selo, texto)

        coluna.addWidget(quem)
        coluna.addWidget(abriu)
        coluna.addSpacing(4)
        coluna.addWidget(selo, 0, Qt.AlignLeft)
        layout.addLayout(coluna, 1)

        return cartao

    def confirmar(self):

        try:
            valor = ler_moeda(self.valor.text())
        except ValueError:
            valor = 0

        if valor < 0:
            QMessageBox.warning(
                self,
                "Atenção",
                "Informe um valor inicial válido.",
            )
            return

        self.accept()

    @property
    def saldo(self):
        try:
            return ler_moeda(self.valor.text())
        except ValueError:
            return 0.0
