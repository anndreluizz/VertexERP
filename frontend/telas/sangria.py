from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from design import tokens
from design.lista import BarraProgresso
from design.privacidade import privacidade
from design.widgets import (
    BotaoPerigo, CampoTexto, DialogoPadrao, FlowLayout, campo_rotulado,
)
from utils.formatacao import formatar_moeda

# painel da gaveta: coluna sempre escura (como o resumo do Pagamento), entao
# estes tons nao trocam com o tema
VERDE_NO_ESCURO = "#4ADE80"
VERMELHO_NO_ESCURO = "#FCA5A5"
AMBAR_NO_ESCURO = "#FBBF24"


class MovimentoGavetaDialog(DialogoPadrao):
    """Base de Sangria e Suprimento: valor (com valores rapidos) + motivo
    (com motivos prontos). Com `esperado` (o que devia ter na gaveta), mostra
    ao lado a gaveta antes e depois do movimento; sem ele (Vendedor nao ve
    totais) fica so' o formulario."""

    TIPO = ""
    # -1 tira dinheiro da gaveta (sangria), +1 poe (suprimento)
    SINAL = -1
    ARTIGO = "DO"   # "DEPOIS DO SUPRIMENTO" / "DEPOIS DA SANGRIA"

    def __init__(
        self, titulo, subtitulo, icone_nome, cor, cor_fundo, placeholder, botao,
        cor_fim, valores, motivos, esperado=None,
    ):

        super().__init__(
            titulo, subtitulo, icone_nome, cor, cor_fundo,
            largura=DialogoPadrao.GRANDE if esperado is not None else DialogoPadrao.PEQUENO,
            cor_fim=cor_fim,
        )

        self._cor = cor
        self._esperado = esperado
        self._chips_valor = {}

        self.valor = QDoubleSpinBox()
        self.valor.setMinimum(0)
        self.valor.setMaximum(99999999)
        self.valor.setDecimals(2)
        self.valor.setPrefix("R$ ")
        self.valor.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.valor.setMinimumHeight(64)
        self.valor.setStyleSheet(f"""
            QDoubleSpinBox {{
                border: 2px solid {tokens.BORDA_CAMPO}; border-radius: {tokens.RADIUS_MD}px;
                padding: 0 16px; font-size: 30px; font-weight: 800;
                color: {tokens.TEXTO}; background: {tokens.CARD};
            }}
            QDoubleSpinBox:focus {{ border-color: {cor}; }}
        """)

        self.descricao = CampoTexto(placeholder)

        esquerda = QVBoxLayout()
        esquerda.setSpacing(10)
        esquerda.addWidget(campo_rotulado("Valor", self.valor))
        esquerda.addLayout(self._linha_valores(valores))
        esquerda.addSpacing(4)
        esquerda.addWidget(campo_rotulado("Motivo", self.descricao))
        esquerda.addLayout(self._linha_motivos(motivos))
        esquerda.addStretch()

        if esperado is None:
            self.corpo.addLayout(esquerda)
        else:
            lado_a_lado = QHBoxLayout()
            lado_a_lado.setSpacing(28)
            lado_a_lado.addLayout(esquerda, 1)
            lado_a_lado.addWidget(self._construir_resumo())
            self.corpo.addLayout(lado_a_lado)
            self.valor.valueChanged.connect(self._atualizar_resumo)

        self.valor.valueChanged.connect(self._pintar_chips_valor)
        self._pintar_chips_valor()
        if esperado is not None:
            self._atualizar_resumo()

        self.bt_confirmar = botao
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.clicked.connect(self.confirmar)
        self.bt_cancelar = self.definir_botoes(self.bt_confirmar)

        self.ajustar_altura()
        self.valor.setFocus()
        self.valor.selectAll()

    # ======================================
    # CHIPS
    # ======================================

    def _linha_valores(self, valores):

        linha = QHBoxLayout()
        linha.setSpacing(8)

        for v in valores:
            bt = QPushButton(f"R$ {v}")
            bt.setCursor(Qt.PointingHandCursor)
            bt.setFixedHeight(40)
            bt.setAutoDefault(False)
            bt.setFocusPolicy(Qt.NoFocus)
            bt.clicked.connect(lambda _=False, x=v: self.valor.setValue(x))
            self._chips_valor[v] = bt
            linha.addWidget(bt, 1)

        return linha

    def _pintar_chips_valor(self, *_):

        fundo_sel = tokens.ERRO_CLARO if self.SINAL < 0 else tokens.SUCESSO_CLARO

        for v, bt in self._chips_valor.items():
            sel = abs(self.valor.value() - v) < 0.005
            bt.setStyleSheet(f"""
                QPushButton {{
                    border:{'2px' if sel else '1px'} solid {self._cor if sel else tokens.BORDA_FORTE};
                    border-radius:{tokens.RADIUS_SM + 2}px;
                    background:{fundo_sel if sel else tokens.CARD};
                    color:{self._cor if sel else tokens.TEXTO};
                    font-weight:600; font-size:{tokens.TAMANHO_SM}px;
                }}
                QPushButton:hover {{ border-color:{self._cor}; }}
            """)

    def _linha_motivos(self, motivos):

        linha = FlowLayout()
        linha.setSpacing(8)

        for texto in motivos:
            bt = QPushButton(texto)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setFixedHeight(30)
            bt.setAutoDefault(False)
            bt.setFocusPolicy(Qt.NoFocus)
            bt.setStyleSheet(f"""
                QPushButton {{
                    padding:0 14px; border-radius:15px; border:1px solid {tokens.BORDA};
                    background:{tokens.CARD}; color:{tokens.TEXTO_SECUNDARIO};
                    font-size:{tokens.TAMANHO_XS}px;
                }}
                QPushButton:hover {{ background:{tokens.FUNDO}; }}
            """)
            bt.clicked.connect(lambda _=False, t=texto: self.descricao.setText(t))
            linha.addWidget(bt)

        return linha

    # ======================================
    # GAVETA ANTES E DEPOIS
    # ======================================

    def _texto(self, cor, tamanho, peso):

        lbl = QLabel()
        self._pintar(lbl, cor, tamanho, peso)
        return lbl

    @staticmethod
    def _pintar(lbl, cor, tamanho, peso):

        lbl.setStyleSheet(
            f"background:transparent; border:none; color:{cor}; "
            f"font-size:{tamanho}px; font-weight:{peso};"
        )

    def _construir_resumo(self):

        painel = QFrame()
        painel.setObjectName("gavetaResumo")
        painel.setFixedWidth(320)
        painel.setStyleSheet(
            f"QFrame#gavetaResumo {{ background:{tokens.SIDEBAR}; border:none; "
            f"border-radius:{tokens.RADIUS_LG}px; }}"
        )

        layout = QVBoxLayout(painel)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(4)

        titulo = self._texto(tokens.TEXTO_SIDEBAR_APAGADO, tokens.TAMANHO_XS, 700)
        titulo.setText("GAVETA")
        layout.addWidget(titulo)
        layout.addSpacing(6)

        agora = self._texto(tokens.TEXTO_SIDEBAR, tokens.TAMANHO_SM, 500)
        agora.setText("Agora")
        layout.addWidget(agora)
        self.lbl_agora = self._texto(tokens.TEXTO_CLARO, 26, 700)
        privacidade.definir_texto(self.lbl_agora, formatar_moeda(self._esperado))
        layout.addWidget(self.lbl_agora)
        layout.addSpacing(10)

        linha = QHBoxLayout()
        self.lbl_acao_rotulo = self._texto(tokens.TEXTO_SIDEBAR, tokens.TAMANHO_SM, 500)
        self.lbl_acao_rotulo.setText(self.cabecalho.titulo.text())
        self.lbl_acao_valor = self._texto(VERDE_NO_ESCURO, tokens.TAMANHO_BASE, 700)
        linha.addWidget(self.lbl_acao_rotulo)
        linha.addStretch()
        linha.addWidget(self.lbl_acao_valor)
        layout.addLayout(linha)

        divisor = QFrame()
        divisor.setFixedHeight(1)
        divisor.setStyleSheet(f"background:{tokens.SIDEBAR_HOVER}; border:none;")
        layout.addSpacing(6)
        layout.addWidget(divisor)
        layout.addSpacing(8)

        self.lbl_depois_rotulo = self._texto(tokens.TEXTO_SIDEBAR_APAGADO, tokens.TAMANHO_XS, 700)
        self.lbl_depois_rotulo.setText(f"DEPOIS {self.ARTIGO} {self.cabecalho.titulo.text().upper()}")
        layout.addWidget(self.lbl_depois_rotulo)
        self.lbl_depois = self._texto(VERDE_NO_ESCURO, 34, 700)
        layout.addWidget(self.lbl_depois)
        layout.addSpacing(10)

        self.barra_gaveta = BarraProgresso(100, VERDE_NO_ESCURO, altura=8)
        # trilho sobre o fundo escuro do painel
        self.barra_gaveta.setStyleSheet(
            f"background:{tokens.SIDEBAR_HOVER}; border:none; border-radius:4px;"
        )
        layout.addWidget(self.barra_gaveta)
        self.lbl_legenda = self._texto(tokens.TEXTO_SIDEBAR, tokens.TAMANHO_XS, 400)
        self.lbl_legenda.setWordWrap(True)
        layout.addWidget(self.lbl_legenda)

        layout.addStretch()

        return painel

    def _atualizar_resumo(self, *_):

        valor = float(self.valor.value())
        depois = round(self._esperado + self.SINAL * valor, 2)

        sinal = "−" if self.SINAL < 0 else "+"
        privacidade.definir_texto(self.lbl_acao_valor, f"{sinal} {formatar_moeda(valor)}")
        privacidade.definir_texto(self.lbl_depois, formatar_moeda(depois))

        if self.SINAL > 0:
            cor, pct = VERDE_NO_ESCURO, 100
            legenda = "Mais dinheiro na gaveta"
        elif depois < 0:
            cor, pct = AMBAR_NO_ESCURO, 0
            legenda = "Mais do que o esperado na gaveta"
        else:
            cor = VERMELHO_NO_ESCURO
            pct = round(depois / self._esperado * 100) if self._esperado > 0 else 0
            legenda = f"{pct}% do esperado fica na gaveta"

        self._pintar(self.lbl_acao_valor, cor, tokens.TAMANHO_BASE, 700)
        self._pintar(self.lbl_depois, cor, 34, 700)
        self.barra_gaveta.definir(pct, cor)
        self.lbl_legenda.setText(legenda)

    # ======================================

    @property
    def dados(self):

        return {
            "tipo": self.TIPO,
            "valor": float(self.valor.value()),
            "descricao": self.descricao.text(),
        }

    def confirmar(self):

        if self.valor.value() <= 0:
            QMessageBox.warning(self, "Aviso", "Informe um valor.")
            self.valor.setFocus()
            return

        if self.descricao.text().strip() == "":
            QMessageBox.warning(self, "Aviso", "Informe uma descrição.")
            self.descricao.setFocus()
            return

        self.accept()


class SangriaWindow(MovimentoGavetaDialog):

    TIPO = "SANGRIA"
    SINAL = -1
    ARTIGO = "DA"

    def __init__(self, esperado=None):
        super().__init__(
            "Sangria", "Retirada de dinheiro da gaveta",
            "arrow-down", tokens.ERRO, tokens.ERRO_CLARO,
            "Motivo da sangria", BotaoPerigo("Confirmar Sangria", icone_nome="check"),
            tokens.ERRO_ESCURA,
            [50, 100, 200, 300, 500],
            ["Levado ao cofre", "Pagamento de fornecedor", "Retirada do dono"],
            esperado,
        )
