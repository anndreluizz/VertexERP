"""Ficha do boleto: abre ao clicar numa conta da lista de Contas a pagar.
Mostra a situação, o valor, o andamento e os detalhes; Editar, Duplicar,
Excluir e Pagar ficam aqui dentro. Não faz nenhuma chamada de rede: quem
abre (ContasPagar) executa a ação escolhida em `acao` depois que ela fecha."""

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QToolTip, QVBoxLayout,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.privacidade import privacidade
from design.widgets import Badge, BotaoPrimario, BotaoSecundario, Card
from services import api
from telas.parcelamento import copiar_codigo_boleto
from utils.formatacao import formatar_moeda
from utils.pix import texto_pra_copiar

# status real -> (texto do selo, variante do Badge, cor, fundo claro, ícone)
_SITUACAO = {
    "VENCIDA": ("Vencida", "erro", "ERRO", "ERRO_CLARO", "alert-triangle"),
    "PENDENTE": ("A vencer", "alerta", "ALERTA_TEXTO", "ALERTA_CLARO", "file-text"),
    "PAGO": ("Paga", "sucesso", "SUCESSO", "SUCESSO_CLARO", "check"),
    "CANCELADO": ("Cancelada", "neutro", "TEXTO_TERCIARIO", "FUNDO", "file-text"),
}


def _data(valor, com_hora=False):
    try:
        return datetime.fromisoformat(valor).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return "—"


def _rotulo(texto, tam=None, cor=None, peso=400, direita=False):
    lbl = QLabel(texto)
    lbl.setStyleSheet(
        f"background:transparent; border:none; color:{cor or tokens.TEXTO};"
        f"font-size:{tam or tokens.TAMANHO_BASE}px; font-weight:{peso};"
    )
    if direita:
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return lbl


def _separador():
    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
    return sep


def _botao_icone(nome, dica, ao_clicar):
    bt = QPushButton()
    bt.setFixedSize(28, 28)
    bt.setCursor(Qt.PointingHandCursor)
    bt.setIcon(icone(nome, cor=tokens.TEXTO_TERCIARIO, tamanho=15))
    bt.setToolTip(dica)
    bt.setAccessibleName(dica)
    bt.setStyleSheet(f"""
        QPushButton {{ border:none; border-radius:6px; background:transparent; }}
        QPushButton:hover {{ background:{tokens.BORDA}; }}
    """)
    bt.clicked.connect(ao_clicar)
    return bt


class FichaBoleto(QDialog):

    def __init__(self, conta, parent=None):
        # import aqui dentro: telas.contas_pagar importa este módulo sob demanda
        from telas.contas_pagar import _status_real, _texto_vencimento

        super().__init__(parent)

        self.conta = conta
        self.acao = None
        status = _status_real(conta)
        texto_selo, variante, cor, fundo, nome_icone = _SITUACAO.get(
            status, _SITUACAO["PENDENTE"]
        )
        cor, fundo = getattr(tokens, cor), getattr(tokens, fundo)

        self.setWindowTitle(conta.get("descricao") or "Conta")
        self.setMinimumWidth(920)
        self.resize(940, 680)
        self.setStyleSheet(f"QDialog {{ background:{tokens.FUNDO}; }}")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        raiz.addWidget(self._construir_cabecalho(status, texto_selo, variante, cor, fundo, nome_icone))

        corpo = QHBoxLayout()
        corpo.setContentsMargins(28, 20, 28, 20)
        corpo.setSpacing(18)
        raiz.addLayout(corpo, 1)

        esquerda = QVBoxLayout()
        esquerda.setSpacing(16)
        esquerda.addWidget(self._construir_valor(status, cor, fundo, _texto_vencimento))
        esquerda.addWidget(self._construir_andamento(status))
        esquerda.addStretch()
        corpo.addLayout(esquerda, 3)

        direita = QVBoxLayout()
        direita.setSpacing(16)
        direita.addWidget(self._construir_detalhes())
        if conta.get("tem_documento"):
            direita.addWidget(self._construir_documento())
        if conta.get("observacao"):
            direita.addWidget(self._construir_observacao())
        direita.addStretch()
        corpo.addLayout(direita, 2)

    # ------------------------------------------------------------------
    # blocos
    # ------------------------------------------------------------------

    def _construir_cabecalho(self, status, texto_selo, variante, cor, fundo, nome_icone):

        conta = self.conta
        quadro = QFrame()
        quadro.setObjectName("CabecalhoFicha")
        quadro.setStyleSheet(
            f"#CabecalhoFicha {{ background:{tokens.CARD}; border:none;"
            f"border-bottom:1px solid {tokens.BORDA}; }}"
        )
        lay = QHBoxLayout(quadro)
        lay.setContentsMargins(28, 20, 24, 18)
        lay.setSpacing(14)

        icone_status = QLabel()
        icone_status.setFixedSize(48, 48)
        icone_status.setAlignment(Qt.AlignCenter)
        icone_status.setStyleSheet(f"background:{fundo}; border-radius:{tokens.RADIUS_MD}px;")
        icone_status.setPixmap(icone_pixmap(nome_icone, cor=cor, tamanho=24))
        lay.addWidget(icone_status)

        col = QVBoxLayout()
        col.setSpacing(3)
        titulo = QHBoxLayout()
        titulo.setSpacing(8)
        titulo.addWidget(_rotulo(conta.get("descricao") or "Despesa", tokens.TAMANHO_XL, peso=700))
        titulo.addWidget(Badge(texto_selo, variante))
        if conta.get("recorrente_id"):
            titulo.addWidget(Badge("Mensal", "info"))
        if conta.get("valor_a_confirmar") and status in ("PENDENTE", "VENCIDA"):
            titulo.addWidget(Badge("Confirmar valor", "alerta"))
        titulo.addStretch()
        col.addLayout(titulo)

        partes = [p for p in (conta.get("categoria"), f"lançada em {_data(conta.get('data_emissao'))}") if p]
        col.addWidget(_rotulo("  ·  ".join(partes), tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO))
        lay.addLayout(col, 1)

        self.bt_editar = BotaoSecundario("Editar", icone_nome="edit-2")
        self.bt_editar.clicked.connect(lambda: self._escolher("editar_despesa"))
        lay.addWidget(self.bt_editar)

        self.bt_mais = BotaoSecundario("", icone_nome="more-vertical")
        self.bt_mais.setFixedWidth(44)
        self.bt_mais.setToolTip("Mais opções")
        self.bt_mais.setAccessibleName("Mais opções")
        self.bt_mais.setMenu(self._construir_menu())
        self.bt_mais.setStyleSheet(
            self.bt_mais.styleSheet() + "QPushButton::menu-indicator { image:none; width:0; }"
        )
        lay.addWidget(self.bt_mais)

        bt_fechar = QPushButton()
        bt_fechar.setFixedSize(34, 34)
        bt_fechar.setCursor(Qt.PointingHandCursor)
        bt_fechar.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=18))
        bt_fechar.setToolTip("Fechar")
        bt_fechar.setAccessibleName("Fechar")
        bt_fechar.setStyleSheet(f"""
            QPushButton {{ border:none; border-radius:17px; background:transparent; }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        bt_fechar.clicked.connect(self.reject)
        lay.addWidget(bt_fechar)
        return quadro

    def _construir_menu(self):

        conta = self.conta
        menu = QMenu(self)
        if conta.get("parcelamento_id"):
            menu.addAction("Ver parcelamento", lambda: self._escolher("ver_parcelamento"))
        if conta.get("pix"):
            menu.addAction("Copiar Pix", self.copiar_pix)
        menu.addAction("Duplicar", lambda: self._escolher("duplicar_despesa"))
        # backend exige contas_pagar.excluir -- sem ela nem mostra
        if api.usuario_tem_permissao("contas_pagar.excluir"):
            menu.addSeparator()
            menu.addAction("Excluir", lambda: self._escolher("excluir_despesa"))
        return menu

    def _construir_valor(self, status, cor, fundo, texto_vencimento):

        conta = self.conta
        cartao = Card()
        lay = QVBoxLayout(cartao)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)

        # faixa de situação
        if status == "PAGO":
            frase = f"Paga em {_data(conta.get('data_pagamento'))}"
            if conta.get("forma_pagamento"):
                frase += f"  ·  {conta['forma_pagamento'].capitalize()}"
        elif status == "CANCELADO":
            frase = "Conta cancelada"
        else:
            frase = texto_vencimento(conta, status)[0]
        faixa = QFrame()
        faixa.setObjectName("FaixaSituacao")
        faixa.setStyleSheet(
            f"#FaixaSituacao {{ background:{fundo}; border:none; border-radius:{tokens.RADIUS_SM}px; }}"
        )
        lf = QHBoxLayout(faixa)
        lf.setContentsMargins(12, 8, 12, 8)
        lf.setSpacing(8)
        marca = QLabel()
        marca.setStyleSheet("background:transparent; border:none;")
        marca.setPixmap(icone_pixmap(_SITUACAO.get(status, _SITUACAO["PENDENTE"])[4], cor=cor, tamanho=16))
        lf.addWidget(marca)
        lf.addWidget(_rotulo(frase, tokens.TAMANHO_BASE, cor, 700))
        lf.addStretch()
        lay.addWidget(faixa)

        lay.addWidget(_rotulo("Valor da conta", tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO, 600))
        valor = QLabel()
        privacidade.definir_texto(valor, formatar_moeda(conta.get("valor", 0)))
        valor.setStyleSheet(
            f"background:transparent; border:none; color:{tokens.TEXTO};"
            "font-size:34px; font-weight:800;"
        )
        lay.addWidget(valor)

        if conta.get("valor_a_confirmar") and status in ("PENDENTE", "VENCIDA"):
            aviso = _rotulo(
                "Valor copiado do mês passado. Quando a fatura chegar, confirme o valor.",
                tokens.TAMANHO_SM, tokens.ALERTA_TEXTO,
            )
            aviso.setWordWrap(True)
            lay.addWidget(aviso)

        botoes = QHBoxLayout()
        botoes.setSpacing(10)
        if status in ("PENDENTE", "VENCIDA"):
            self.bt_pagar = BotaoPrimario("Pagar agora", icone_nome="check")
            self.bt_pagar.setMinimumHeight(44)
            self.bt_pagar.clicked.connect(lambda: self._escolher("pagar_despesa"))
            botoes.addWidget(self.bt_pagar)
            if conta.get("numero_boleto"):
                bt = BotaoSecundario("Copiar código do boleto", icone_nome="copy")
                bt.setMinimumHeight(44)
                bt.clicked.connect(self.copiar_codigo)
                botoes.addWidget(bt)
        elif conta.get("tem_comprovante_pagamento"):
            bt = BotaoSecundario("Ver comprovante", icone_nome="file-text")
            bt.setMinimumHeight(44)
            bt.clicked.connect(lambda: self._escolher("ver_comprovante"))
            botoes.addWidget(bt)
        botoes.addStretch()
        lay.addLayout(botoes)
        return cartao

    def _construir_andamento(self, status):

        conta = self.conta
        cartao = Card()
        lay = QVBoxLayout(cartao)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(2)
        lay.addWidget(_rotulo("Andamento", tokens.TAMANHO_MD, peso=700))
        lay.addSpacing(8)

        vence = _data(conta.get("data_vencimento"))
        passos = [
            ("plus", tokens.PRIMARIA, tokens.PRIMARIA_CLARA, "Conta lançada", _data(conta.get("data_emissao")), True),
            (
                "calendar",
                tokens.ERRO if status == "VENCIDA" else tokens.PRIMARIA,
                tokens.ERRO_CLARO if status == "VENCIDA" else tokens.PRIMARIA_CLARA,
                "Vencimento", vence, True,
            ),
            (
                "check", tokens.SUCESSO, tokens.SUCESSO_CLARO, "Pagamento",
                _data(conta.get("data_pagamento")) if status == "PAGO" else "Ainda não paga",
                status == "PAGO",
            ),
        ]
        for indice, (nome, cor, fundo, titulo, sub, feito) in enumerate(passos):
            lay.addLayout(self._passo(nome, cor, fundo, titulo, sub, feito, indice == len(passos) - 1))
        return cartao

    def _passo(self, nome, cor, fundo, titulo, sub, feito, ultimo):

        linha = QHBoxLayout()
        linha.setSpacing(12)

        col = QVBoxLayout()
        col.setSpacing(0)
        col.setAlignment(Qt.AlignTop)
        bolinha = QLabel()
        bolinha.setFixedSize(30, 30)
        bolinha.setAlignment(Qt.AlignCenter)
        if feito:
            bolinha.setPixmap(icone_pixmap(nome, cor=cor, tamanho=15))
            bolinha.setStyleSheet(f"background:{fundo}; border-radius:15px; border:none;")
        else:
            bolinha.setStyleSheet(
                f"background:{tokens.CARD}; border:1.5px dashed {tokens.BORDA_FORTE}; border-radius:15px;"
            )
        col.addWidget(bolinha, 0, Qt.AlignHCenter)
        if not ultimo:
            traco = QFrame()
            traco.setFixedSize(2, 22)
            traco.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
            col.addWidget(traco, 0, Qt.AlignHCenter)
        linha.addLayout(col)

        texto = QVBoxLayout()
        texto.setSpacing(0)
        texto.addWidget(_rotulo(titulo, tokens.TAMANHO_BASE, peso=600 if feito else 500))
        texto.addWidget(_rotulo(sub, tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO))
        linha.addLayout(texto, 1)
        return linha

    def _linha_info(self, rotulo, valor, copiar=None):

        linha = QHBoxLayout()
        linha.setContentsMargins(0, 9, 0, 9)
        linha.setSpacing(10)
        linha.addWidget(_rotulo(rotulo, tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO))
        linha.addStretch()
        vazio = not valor
        linha.addWidget(_rotulo(
            valor or "—", tokens.TAMANHO_SM,
            tokens.TEXTO_TERCIARIO if vazio else tokens.TEXTO, 700, direita=True,
        ))
        if copiar and not vazio:
            linha.addWidget(_botao_icone("copy", "Copiar", copiar))
        return linha

    def _construir_detalhes(self):

        conta = self.conta
        cartao = Card()
        lay = QVBoxLayout(cartao)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(0)
        lay.addWidget(_rotulo("Detalhes", tokens.TAMANHO_MD, peso=700))
        lay.addSpacing(4)

        if conta.get("parcelamento_id") and conta.get("parcela_total"):
            repeticao = f"Parcela {conta.get('parcela_numero') or '?'} de {conta['parcela_total']}"
        elif conta.get("recorrente_id"):
            repeticao = "Todo mês"
        else:
            repeticao = "Uma vez"

        numero = conta.get("numero_boleto") or ""
        linhas = [
            ("Categoria", conta.get("categoria"), None),
            ("Repetição", repeticao, None),
            ("Centro de custo", conta.get("centro_custo"), None),
            ("Plano de contas", conta.get("plano_conta_nome"), None),
            ("Linha digitável", numero, self.copiar_codigo),
            ("Chave Pix", texto_pra_copiar(conta.get("pix"))[:28] if conta.get("pix") else "", self.copiar_pix),
        ]
        if conta.get("status") == "PAGO":
            linhas += [
                ("Banco", conta.get("banco_pagamento"), None),
                ("Nº da transação", conta.get("numero_transacao"), None),
            ]
        for indice, (rotulo, valor, copiar) in enumerate(linhas):
            lay.addLayout(self._linha_info(rotulo, valor, copiar))
            if indice < len(linhas) - 1:
                lay.addWidget(_separador())
        return cartao

    def _construir_documento(self):

        cartao = Card()
        lay = QVBoxLayout(cartao)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)
        lay.addWidget(_rotulo("Documento", tokens.TAMANHO_MD, peso=700))

        linha = QHBoxLayout()
        linha.setSpacing(12)
        quadro = QLabel()
        quadro.setFixedSize(40, 40)
        quadro.setAlignment(Qt.AlignCenter)
        quadro.setPixmap(icone_pixmap("file-text", cor=tokens.PRIMARIA, tamanho=20))
        quadro.setStyleSheet(
            f"background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_SM + 2}px; border:none;"
        )
        linha.addWidget(quadro)
        linha.addWidget(
            _rotulo(self.conta.get("documento_nome") or "Documento anexado", tokens.TAMANHO_BASE, peso=600), 1
        )
        bt = BotaoSecundario("Ver")
        bt.setMinimumHeight(34)
        bt.clicked.connect(lambda: self._escolher("ver_documento"))
        linha.addWidget(bt)
        lay.addLayout(linha)
        return cartao

    def _construir_observacao(self):

        cartao = Card()
        lay = QVBoxLayout(cartao)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(6)
        lay.addWidget(_rotulo("OBSERVAÇÕES", tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO, 800))
        texto = _rotulo(self.conta["observacao"], tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO)
        texto.setWordWrap(True)
        lay.addWidget(texto)
        return cartao

    # ------------------------------------------------------------------
    # ações
    # ------------------------------------------------------------------

    def _escolher(self, acao):
        """Fecha a ficha e deixa a tela de contas executar a ação."""
        self.acao = acao
        self.accept()

    def copiar_codigo(self):
        copiar_codigo_boleto(self.conta.get("numero_boleto"))

    def copiar_pix(self):
        texto = texto_pra_copiar(self.conta.get("pix"))
        if texto:
            QGuiApplication.clipboard().setText(texto)
            QToolTip.showText(QCursor.pos(), "Pix copiado! Cole no app do banco.")
