"""Cadastro em etapas: poucos campos por vez, barra de progresso, erro só no
campo errado, Enter vai pro campo seguinte (e avança no último).

`AssistenteDialogo` só cuida da conversa; quem salva é o diálogo de cadastro
de sempre, que o assistente preenche por trás (`interno`) e manda salvar --
assim a validação e o salvamento continuam os mesmos. Atributos que o
assistente não tem (cliente_salvo, dados...) saem do `interno`, então quem já
chamava `Dialogo().exec()` e lia o resultado nele continua funcionando."""

from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox, QDateEdit, QDialog, QDoubleSpinBox, QFrame,
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.seletor import Seletor
from design.widgets import BotaoPrimario, BotaoSecundario, BotaoSucesso, CampoTexto

_ESTILO_CAMPO = (
    f"border:1.5px solid {tokens.BORDA_CAMPO}; border-radius:{tokens.RADIUS_SM}px;"
    f"padding:0 14px; font-size:{tokens.TAMANHO_MD}px; background:{tokens.CARD};"
    f"color:{tokens.TEXTO};"
)


def _rotulo(texto, tam=None, cor=None, peso=400):
    lbl = QLabel(texto)
    lbl.setStyleSheet(
        f"background:transparent; border:none; color:{cor or tokens.TEXTO};"
        f"font-size:{tam or tokens.TAMANHO_BASE}px; font-weight:{peso};"
    )
    return lbl


def _chip(texto):
    bt = QPushButton(texto)
    bt.setFixedHeight(32)
    bt.setCursor(Qt.PointingHandCursor)
    bt.setAutoDefault(False)
    bt.setStyleSheet(f"""
        QPushButton {{
            padding:0 14px; border-radius:16px; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; border:1px solid {tokens.BORDA_FORTE};
            background:{tokens.CARD}; color:{tokens.TEXTO_SECUNDARIO};
        }}
        QPushButton:hover {{
            background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA};
            border-color:{tokens.PRIMARIA};
        }}
    """)
    return bt


# ----------------------------------------------------------------------
# campos
# ----------------------------------------------------------------------

def campo_dinheiro():
    """Valor em reais, sem as setinhas de subir/descer (digita-se o valor)."""
    c = QDoubleSpinBox()
    c.setDecimals(2)
    c.setMaximum(999999.99)
    c.setPrefix("R$ ")
    c.setMinimumHeight(44)
    c.setButtonSymbols(QAbstractSpinBox.NoButtons)
    c.setStyleSheet(f"QDoubleSpinBox {{ {_ESTILO_CAMPO} }} QDoubleSpinBox:focus {{ border-color:{tokens.PRIMARIA}; }}")
    return c


class Opcoes(QWidget):
    """Botões de opção (escolha única) no lugar de uma lista suspensa."""

    def __init__(self, itens, atual=0):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        self.mudou = None
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(8)
        self._lay.addStretch()
        self.botoes = []
        self.atual = 0
        for t in itens:
            self._novo(t)
        if self.botoes:
            self.marcar(atual)

    def _novo(self, texto):
        bt = QPushButton(texto)
        bt.setFixedHeight(44)
        bt.setMinimumWidth(96)
        bt.setCursor(Qt.PointingHandCursor)
        bt.setAutoDefault(False)
        i = len(self.botoes)
        bt.clicked.connect(lambda _=False, k=i: self.marcar(k))
        self.botoes.append(bt)
        self._lay.insertWidget(self._lay.count() - 1, bt)

    def adicionar(self, texto):
        self._novo(texto)
        self.marcar(len(self.botoes) - 1)

    def marcar(self, i):
        self.atual = i
        for j, bt in enumerate(self.botoes):
            on = j == i
            bt.setStyleSheet(f"""
                QPushButton {{
                    padding:0 18px; border-radius:{tokens.RADIUS_SM + 2}px;
                    font-size:{tokens.TAMANHO_BASE}px; font-weight:{700 if on else 600};
                    border:1.5px solid {tokens.PRIMARIA if on else tokens.BORDA_CAMPO};
                    background:{tokens.PRIMARIA_CLARA if on else tokens.CARD};
                    color:{tokens.PRIMARIA if on else tokens.TEXTO_SECUNDARIO};
                }}
                QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA if on else tokens.FUNDO}; }}
            """)
        if self.mudou:
            self.mudou(i)

    def texto(self):
        return self.botoes[self.atual].text() if self.botoes else ""


class Escolha(QWidget):
    """Escolha de uma opção de uma lista: botões quando são poucas, botão
    com menu e busca quando são muitas. Com `ao_criar`, mostra "Nova ..."
    com um campo na hora; `ao_criar(nome)` é quem cria de verdade."""

    MAX_BOTOES = 5

    def __init__(self, itens, atual=None, rotulo_nova=None, ao_criar=None):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        self._ao_criar = ao_criar
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        itens = list(itens)
        if not itens and not ao_criar:
            lay.addWidget(_rotulo(
                "Nenhuma cadastrada ainda. Você cria depois, em Editar.",
                tokens.TAMANHO_SM, tokens.TEXTO_TERCIARIO,
            ))
        self._botoes = len(itens) <= self.MAX_BOTOES
        if self._botoes:
            self._opcoes = Opcoes(itens, itens.index(atual) if atual in itens else 0)
            lay.addWidget(self._opcoes)
        else:
            self._seletor = Seletor(campo=True)
            self._seletor.addItems(itens)
            self._seletor.setMinimumHeight(44)
            self._seletor.setStyleSheet(f"QComboBox {{ {_ESTILO_CAMPO} }}")
            if atual in itens:
                self._seletor.setCurrentText(atual)
            lay.addWidget(self._seletor)

        if rotulo_nova and ao_criar:
            self.bt_nova = BotaoSecundario(rotulo_nova, icone_nome="plus")
            self.bt_nova.setMinimumHeight(36)
            self.bt_nova.clicked.connect(self._alternar_nova)
            lay.addWidget(self.bt_nova, 0, Qt.AlignLeft)

            self._nova = QWidget()
            ln = QHBoxLayout(self._nova)
            ln.setContentsMargins(0, 0, 0, 0)
            ln.setSpacing(8)
            self.campo_nova = CampoTexto("Nome")
            self.campo_nova.returnPressed.connect(self._criar)
            bt = BotaoPrimario("Criar", icone_nome="check")
            bt.clicked.connect(self._criar)
            ln.addWidget(self.campo_nova, 1)
            ln.addWidget(bt)
            self._nova.hide()
            lay.addWidget(self._nova)

    def _alternar_nova(self):
        self._nova.setVisible(not self._nova.isVisible())
        if self._nova.isVisible():
            self.campo_nova.setFocus()

    def _criar(self):
        nome = self.campo_nova.text().strip()
        if nome:
            self._ao_criar(nome)
            self.campo_nova.clear()
            self._nova.hide()

    def adicionar(self, texto):
        if self._botoes:
            self._opcoes.adicionar(texto)
        else:
            if self._seletor.findText(texto) < 0:
                self._seletor.addItem(texto)
            self._seletor.setCurrentText(texto)

    def texto(self):
        return self._opcoes.texto() if self._botoes else self._seletor.currentText()

    def setFocus(self):
        (self._opcoes if self._botoes else self._seletor).setFocus()


class Contador(QWidget):
    """Quantidade com botões − e + redondos (no lugar das setinhas)."""

    def __init__(self, valor=0, minimo=0, casas=0):
        super().__init__()
        self.minimo, self.casas, self._n = minimo, casas, float(valor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        def botao(nome, passo):
            bt = QPushButton()
            bt.setFixedSize(44, 44)
            bt.setAutoDefault(False)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setIcon(icone(nome, cor=tokens.TEXTO_SECUNDARIO, tamanho=20))
            bt.setAccessibleName("Diminuir" if passo < 0 else "Aumentar")
            bt.setStyleSheet(f"""
                QPushButton {{
                    border:1.5px solid {tokens.BORDA_CAMPO}; border-radius:22px;
                    background:{tokens.CARD};
                }}
                QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA}; border-color:{tokens.PRIMARIA}; }}
            """)
            bt.clicked.connect(lambda: self.definir(self._n + passo))
            return bt

        self.campo = CampoTexto("0")
        self.campo.setFixedWidth(110)
        self.campo.setAlignment(Qt.AlignCenter)
        self.campo.editingFinished.connect(lambda: self.definir(self._ler(self.campo.text())))
        self.campo.textEdited.connect(lambda t: setattr(self, "_n", self._ler(t)))
        lay.addWidget(botao("minus", -1))
        lay.addWidget(self.campo)
        lay.addWidget(botao("plus", 1))
        lay.addStretch()
        self.definir(valor)

    @staticmethod
    def _ler(texto):
        try:
            return float((texto or "0").replace(",", "."))
        except ValueError:
            return 0.0

    def definir(self, valor):
        self._n = max(float(self.minimo), round(float(valor), self.casas))
        self.campo.setText(f"{self._n:.{self.casas}f}".replace(".", ",") if self.casas else str(int(self._n)))

    def value(self):
        return self._n

    def text(self):
        return self.campo.text()

    def setFocus(self):
        self.campo.setFocus()


class ValoresRapidos(QWidget):
    """Dinheiro + atalhos de valor (tocar preenche)."""

    def __init__(self, valores):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.campo = campo_dinheiro()
        lay.addWidget(self.campo)
        linha = QHBoxLayout()
        linha.setSpacing(8)
        for v in valores:
            bt = _chip(f"R$ {v:,.0f}".replace(",", "."))
            bt.clicked.connect(lambda _=False, v=v: self.campo.setValue(v))
            linha.addWidget(bt)
        linha.addStretch()
        lay.addLayout(linha)

    def value(self):
        return self.campo.value()

    def setValue(self, v):
        self.campo.setValue(v)

    def text(self):
        return str(self.campo.value())

    def setFocus(self):
        self.campo.setFocus()


class DataRapida(QWidget):
    """Data com calendário + atalhos (Hoje, Amanhã, em 7 dias, em 30 dias)."""

    def __init__(self, data=None):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.campo = QDateEdit(data or QDate.currentDate().addDays(7))
        self.campo.setCalendarPopup(True)
        self.campo.setDisplayFormat("dd/MM/yyyy")
        self.campo.setMinimumHeight(44)
        self.campo.setStyleSheet(f"""
            QDateEdit {{ {_ESTILO_CAMPO} }}
            QDateEdit:focus {{ border-color:{tokens.PRIMARIA}; }}
            QDateEdit::drop-down {{ width:0; border:none; }}
        """)
        lay.addWidget(self.campo)
        linha = QHBoxLayout()
        linha.setSpacing(8)
        for texto, dias in (("Hoje", 0), ("Amanhã", 1), ("Em 7 dias", 7), ("Em 30 dias", 30)):
            bt = _chip(texto)
            bt.clicked.connect(lambda _=False, d=dias: self.campo.setDate(QDate.currentDate().addDays(d)))
            linha.addWidget(bt)
        linha.addStretch()
        lay.addLayout(linha)

    def date(self):
        return self.campo.date()

    def text(self):
        return self.campo.text()

    def setFocus(self):
        self.campo.setFocus()


# ----------------------------------------------------------------------
# campo da etapa: rótulo + widget + erro próprio
# ----------------------------------------------------------------------

class CampoEtapa(QWidget):
    """`valida(widget)` devolve a mensagem de erro (ou None). O erro aparece
    embaixo deste campo e some assim que a pessoa mexe nele."""

    def __init__(self, rotulo, widget, obrigatorio=False, valida=None, dica=None):
        super().__init__()
        self.w, self.obrigatorio, self.valida = widget, obrigatorio, valida
        self._estilo_base = widget.styleSheet()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        topo = QHBoxLayout()
        topo.addWidget(_rotulo(rotulo, tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO, 700))
        topo.addWidget(_rotulo(
            "obrigatório" if obrigatorio else "opcional", tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO
        ))
        topo.addStretch()
        lay.addLayout(topo)
        lay.addWidget(widget)

        self.erro = _rotulo("", tokens.TAMANHO_XS, tokens.ERRO, 600)
        self.erro.hide()
        lay.addWidget(self.erro)
        if dica:
            lay.addWidget(_rotulo(dica, tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO))

        for sinal in ("textChanged", "valueChanged", "dateChanged"):
            if hasattr(widget, sinal):
                getattr(widget, sinal).connect(lambda *_: self.limpar())

    def _vazio(self):
        w = self.w
        if isinstance(w, (QDoubleSpinBox, ValoresRapidos, Contador)):
            return w.value() <= 0
        if isinstance(w, (Escolha, Opcoes)):
            return not w.texto()
        return not str(w.text()).strip()

    def checar(self):
        msg = None
        if self.obrigatorio and self._vazio():
            msg = "Preencha este campo para continuar."
        elif self.valida and not self._vazio():
            msg = self.valida(self.w)
        if msg:
            self.erro.setText(msg)
            self.erro.show()
            self.w.setStyleSheet(
                self._estilo_base
                + f"QLineEdit, QDoubleSpinBox, QDateEdit {{ border:1.5px solid {tokens.ERRO}; }}"
            )
        return msg is None

    def limpar(self):
        if not self.erro.isHidden():
            self.erro.hide()
            self.w.setStyleSheet(self._estilo_base)

    def focar(self):
        self.w.setFocus()


# ----------------------------------------------------------------------
# o assistente
# ----------------------------------------------------------------------

class AssistenteDialogo(QDialog):
    """passos: lista de dict(nome, titulo, dica, campos=callable -> [CampoEtapa],
    opcional=bool) e o último com revisao=True e resumo=callable -> [(rótulo, valor)].
    Os campos de cada etapa são criados na primeira vez que ela abre (assim uma
    etapa pode usar o que já foi preenchido antes) e guardados."""

    def __init__(self, titulo, icone_nome, passos, rotulo_final, ao_concluir, interno=None, parent=None):
        super().__init__(parent)
        self.interno = interno
        self._passos, self._i, self._cache = passos, 0, {}
        self._rotulo_final, self._ao_concluir = rotulo_final, ao_concluir
        self.setWindowTitle(titulo)
        self.setMinimumSize(720, 620)
        self.resize(720, 640)
        self.setStyleSheet(f"QDialog {{ background:{tokens.CARD}; }}")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        cab = QHBoxLayout()
        cab.setContentsMargins(28, 22, 24, 14)
        cab.setSpacing(12)
        ic = QLabel()
        ic.setFixedSize(40, 40)
        ic.setAlignment(Qt.AlignCenter)
        ic.setPixmap(icone_pixmap(icone_nome, cor=tokens.PRIMARIA, tamanho=20))
        ic.setStyleSheet(f"background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_SM + 2}px;")
        cab.addWidget(ic)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(_rotulo(titulo, tokens.TAMANHO_XL, peso=700))
        self.lbl_etapa = _rotulo("", tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO)
        col.addWidget(self.lbl_etapa)
        cab.addLayout(col, 1)
        fechar = QPushButton()
        fechar.setFixedSize(34, 34)
        fechar.setAutoDefault(False)
        fechar.setCursor(Qt.PointingHandCursor)
        fechar.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=18))
        fechar.setToolTip("Fechar")
        fechar.setAccessibleName("Fechar")
        fechar.setStyleSheet(f"""
            QPushButton {{ border:none; border-radius:17px; background:transparent; }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        fechar.clicked.connect(self.reject)
        cab.addWidget(fechar)
        raiz.addLayout(cab)

        barra = QHBoxLayout()
        barra.setContentsMargins(28, 0, 28, 0)
        barra.setSpacing(6)
        self._segmentos = []
        for _ in passos:
            seg = QFrame()
            seg.setFixedHeight(6)
            self._segmentos.append(seg)
            barra.addWidget(seg)
        raiz.addLayout(barra)

        nomes = QHBoxLayout()
        nomes.setContentsMargins(28, 8, 28, 0)
        nomes.setSpacing(6)
        self._nomes = []
        for p in passos:
            lbl = _rotulo(p["nome"], tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO, 700)
            self._nomes.append(lbl)
            nomes.addWidget(lbl, 1)
        raiz.addLayout(nomes)

        self._corpo = QVBoxLayout()
        self._corpo.setContentsMargins(28, 26, 28, 10)
        self._corpo.setSpacing(18)
        raiz.addLayout(self._corpo, 1)

        rodape = QFrame()
        rodape.setObjectName("RodapeAssistente")
        rodape.setStyleSheet(
            f"#RodapeAssistente {{ background:{tokens.CARD}; border:none; border-top:1px solid {tokens.BORDA}; }}"
        )
        lr = QHBoxLayout(rodape)
        lr.setContentsMargins(28, 14, 28, 14)
        lr.setSpacing(10)
        lr.addWidget(_rotulo("Enter avança  ·  Esc fecha", tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO))
        lr.addStretch()
        self.bt_voltar = BotaoSecundario("Voltar", icone_nome="chevron-left")
        self.bt_voltar.clicked.connect(lambda: self._ir(self._i - 1))
        lr.addWidget(self.bt_voltar)
        self.bt_pular = QPushButton("Pular")
        self.bt_pular.setCursor(Qt.PointingHandCursor)
        self.bt_pular.setAutoDefault(False)
        self.bt_pular.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; color:{tokens.TEXTO_SECUNDARIO};
                           font-weight:600; font-size:{tokens.TAMANHO_BASE}px; padding:0 14px; }}
            QPushButton:hover {{ color:{tokens.TEXTO}; }}
        """)
        self.bt_pular.clicked.connect(lambda: self._ir(self._i + 1))
        lr.addWidget(self.bt_pular)
        self.bt_proximo = BotaoPrimario("Próximo", icone_nome="chevron-right")
        self.bt_proximo.setMinimumWidth(170)
        self.bt_proximo.clicked.connect(self.avancar)
        lr.addWidget(self.bt_proximo)
        raiz.addWidget(rodape)

        for tecla in (Qt.Key_Return, Qt.Key_Enter):
            QShortcut(QKeySequence(tecla), self, activated=self.enter)

        self._ir(0)

    def __getattr__(self, nome):
        # o que o assistente não tem vem do diálogo de cadastro por trás
        interno = self.__dict__.get("interno")
        if interno is None or nome.startswith("__"):
            raise AttributeError(nome)
        return getattr(interno, nome)

    # ------------------------------------------------------------------

    def _limpar_corpo(self):
        while self._corpo.count():
            item = self._corpo.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().setParent(None)

    def _ir(self, n):
        n = max(0, min(n, len(self._passos) - 1))
        self._i = n
        p = self._passos[n]
        ultimo = n == len(self._passos) - 1
        self.lbl_etapa.setText(f"Etapa {n + 1} de {len(self._passos)}  ·  {p['nome']}")
        for j, seg in enumerate(self._segmentos):
            seg.setStyleSheet(
                f"background:{tokens.PRIMARIA if j <= n else tokens.BORDA}; border-radius:3px;"
            )
        for j, lbl in enumerate(self._nomes):
            lbl.setStyleSheet(
                f"background:transparent; color:{tokens.PRIMARIA if j == n else tokens.TEXTO_TERCIARIO};"
                f"font-size:{tokens.TAMANHO_XS}px; font-weight:{800 if j == n else 600};"
            )

        self._limpar_corpo()
        self._corpo.addWidget(_rotulo(p["titulo"], 24, peso=800))
        dica = _rotulo(p["dica"], tokens.TAMANHO_BASE, tokens.TEXTO_SECUNDARIO)
        dica.setWordWrap(True)
        self._corpo.addWidget(dica)
        self._corpo.addSpacing(4)

        if p.get("revisao"):
            self._corpo.addWidget(self._revisao(p))
            self._campos = []
        else:
            if n not in self._cache:
                self._cache[n] = p["campos"]()
            self._campos = self._cache[n]
            for c in self._campos:
                c.show()
                self._corpo.addWidget(c)
            QTimer.singleShot(0, lambda c=self._campos[0]: self._focar(c))
        self._corpo.addStretch()

        self.bt_voltar.setVisible(n > 0)
        self.bt_pular.setVisible(bool(p.get("opcional")) and not ultimo)
        self.bt_proximo.setText(self._rotulo_final if ultimo else "Próximo")
        self.bt_proximo.setIcon(icone("check" if ultimo else "chevron-right", cor=tokens.TEXTO_CLARO, tamanho=18))

    @staticmethod
    def _focar(campo):
        try:
            campo.focar()
        except RuntimeError:  # a etapa já foi trocada/fechada
            pass

    def _revisao(self, p):
        from design.widgets import Card

        cartao = Card()
        lay = QVBoxLayout(cartao)
        lay.setContentsMargins(18, 10, 18, 10)
        lay.setSpacing(0)
        linhas = p["resumo"]()
        for i, (rotulo, valor) in enumerate(linhas):
            linha = QHBoxLayout()
            linha.setContentsMargins(0, 9, 0, 9)
            linha.addWidget(_rotulo(rotulo, tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO))
            linha.addStretch()
            linha.addWidget(_rotulo(
                valor or "—", tokens.TAMANHO_BASE,
                tokens.TEXTO if valor else tokens.TEXTO_TERCIARIO, 700,
            ))
            lay.addLayout(linha)
            if i < len(linhas) - 1:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
                lay.addWidget(sep)
        return cartao

    def enter(self):
        """Enter: vai pro próximo campo da etapa; no último, avança."""
        foco = self.focusWidget()
        for n, c in enumerate(self._campos[:-1]):
            if foco is not None and (foco is c.w or c.w.isAncestorOf(foco)):
                self._campos[n + 1].focar()
                return
        self.avancar()

    def avancar(self):
        if not self.bt_proximo.isEnabled():
            return
        if self._passos[self._i].get("revisao"):
            self.bt_proximo.setEnabled(False)
            self._ao_concluir(self)
            return
        ok = [c.checar() for c in self._campos]
        if all(ok):
            self._ir(self._i + 1)
        else:
            next(c for c, o in zip(self._campos, ok) if not o).focar()

    def liberar(self):
        """O salvamento falhou: deixa tentar de novo."""
        self.bt_proximo.setEnabled(True)

    def aguardar_salvamento(self, botao_salvar):
        """O salvamento do diálogo por trás é assíncrono: reabilita o botão
        final quando ele terminar sem aceitar (erro)."""
        def checar():
            if not self.isVisible():
                return
            if botao_salvar.isEnabled():
                self.liberar()
            else:
                QTimer.singleShot(250, checar)
        QTimer.singleShot(250, checar)
