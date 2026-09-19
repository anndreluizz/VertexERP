import csv
import json
from datetime import date, datetime
from urllib.parse import quote

from PySide6.QtCore import Qt, QDate, QUrl, Signal
from PySide6.QtGui import (
    QColor, QDesktopServices, QFont, QPageSize, QPainter, QPainterPath,
    QPixmap, QTextDocument,
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QDateEdit,
    QPushButton,
    QFrame,
    QFileDialog,
    QScrollArea,
    QMessageBox,
    QInputDialog,
    QMenu,
    QWidget,
)

from services import api
from services.produto_service import listar_produtos
from services.venda_service import listar_vendas
from services.movimento_fiado_service import (
    saldo_cliente,
    listar_movimentos_cliente,
    registrar_pagamento,
    lancar_fiado_manual,
    lancar_haver,
    editar_movimento,
    excluir_movimento,
)
from services.cliente_service import (
    obter_foto_cliente,
    listar_observacoes_cliente,
    criar_observacao_cliente,
    excluir_observacao_cliente,
    enviar_whatsapp_texto,
)
from telas import comprovante_acoes
from services import cliente_analise
from services import comprovante_service, impressora_termica_service, preferencias_service
from services.worker import rodar_em_thread, em_paralelo


def _buscar_dados_recibo_pagamento(cliente_id, valor, momento):
    """Roda na worker thread -- valor/momento so' viajam de ida e volta
    junto com o resultado (ver services/worker.py: callback precisa
    ser metodo vinculado, nao lambda/closure). As 3 chamadas de rede
    sao independentes, entao disparam em paralelo."""
    saldo_depois, usuario, config_loja = em_paralelo(
        (saldo_cliente, cliente_id), (api.me,), (api.configuracoes,)
    )
    responsavel = (usuario or {}).get("nome") or "—"
    return saldo_depois, responsavel, config_loja, valor, momento


def _buscar_dados_ficha_cliente(cliente_id):
    """Roda na worker thread -- as 4 chamadas que
    FichaClienteDialog.carregar() precisa, independentes entre si,
    disparadas em paralelo."""
    saldo, vendas, produtos, movimentos = em_paralelo(
        (saldo_cliente, cliente_id),
        (listar_vendas,),
        (listar_produtos,),
        (listar_movimentos_cliente, cliente_id),
    )
    vendas_por_id = {v["id"]: v for v in vendas}
    nomes_produto = {p["id"]: p["nome"] for p in produtos}
    return saldo, vendas_por_id, nomes_produto, movimentos

from design import tokens
from design.icons import icone, icone_pixmap
from design.responsive import tamanho_fixo_seguro
from utils.formatacao import formatar_moeda
from design.widgets import (
    Avatar,
    Badge,
    BotaoPerigo,
    BotaoPrimario,
    BotaoSecundario,
    BotaoSucesso,
    CampoTexto,
    Card,
    FlowLayout,
    SecaoCard,
)


def _pixmap_circular(pixmap, tamanho):
    """Recorta um QPixmap qualquer num círculo — usado pra mostrar a foto
    do cliente no lugar das iniciais do Avatar, sem perder o formato
    redondo padrão do design system (setStyleSheet com border-radius não
    recorta o conteúdo de um pixmap, só o fundo do widget)."""

    escalado = pixmap.scaled(
        tamanho, tamanho, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    )

    resultado = QPixmap(tamanho, tamanho)
    resultado.fill(Qt.transparent)

    pintor = QPainter(resultado)
    pintor.setRenderHint(QPainter.Antialiasing)

    caminho = QPainterPath()
    caminho.addEllipse(0, 0, tamanho, tamanho)
    pintor.setClipPath(caminho)

    x = (tamanho - escalado.width()) // 2
    y = (tamanho - escalado.height()) // 2
    pintor.drawPixmap(x, y, escalado)
    pintor.end()

    return resultado


FORMAS_PAGAMENTO = [
    ("Dinheiro", "DINHEIRO"),
    ("PIX", "PIX"),
    ("Cartão", "CARTAO"),
    ("Transferência", "TRANSFERENCIA"),
    ("Cheque", "CHEQUE"),
]

NOMES_FORMA_FIADO = {valor: rotulo for rotulo, valor in FORMAS_PAGAMENTO}

_ICONES_FORMA_PAGAMENTO = {
    "DINHEIRO": "dollar-sign",
    "PIX": "refresh-cw",
    "CARTAO": "credit-card",
    "TRANSFERENCIA": "arrow-up",
    "CHEQUE": "file-text",
}


def _parse_data(texto):
    try:
        return datetime.fromisoformat(texto)
    except (ValueError, TypeError):
        return None


def _botao_data_rapida(rotulo, campo_data, delta_dias):
    """Botão "Hoje"/"Ontem" que preenche um QDateEdit num clique só --
    evita abrir o calendário toda vez pra um lançamento que quase
    sempre é datado de hoje (ou, no máximo, ontem)."""

    bt = QPushButton(rotulo)
    bt.setCursor(Qt.PointingHandCursor)
    bt.setAutoDefault(False)
    bt.setFixedHeight(44)
    bt.setStyleSheet(f"""
        QPushButton {{
            background:{tokens.CARD}; border:1.5px solid {tokens.BORDA};
            border-radius:{tokens.RADIUS_SM}px; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700; padding:0 14px;
        }}
        QPushButton:hover {{ border-color:{tokens.PRIMARIA}; color:{tokens.PRIMARIA}; }}
    """)
    bt.clicked.connect(
        lambda: campo_data.setDate(QDate.currentDate().addDays(delta_dias))
    )
    return bt


class _OpcaoTipoRegistro(QFrame):
    """Cartão selecionável (título + descrição) -- mesmo princípio
    visual das pílulas de forma de pagamento, só que maior e com duas
    linhas de texto. Puramente de apresentação: só muda a dica do
    campo Descrição, não existe distinção real no backend entre "nova
    compra" e "dívida anterior" quando lançado por aqui (os dois viram
    o mesmo tipo de movimento -- COMPRA sem venda_id)."""

    clicado = Signal()

    def __init__(self, titulo, subtitulo, parent=None):

        super().__init__(parent)

        self.selecionado = False
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_SM}px;
            font-weight:700; color:{tokens.TEXTO};
        """)

        lbl_subtitulo = QLabel(subtitulo)
        lbl_subtitulo.setWordWrap(True)
        lbl_subtitulo.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(lbl_titulo)
        layout.addWidget(lbl_subtitulo)

        self._pintar()

    def _pintar(self):

        cor_borda = tokens.PRIMARIA if self.selecionado else tokens.BORDA
        cor_fundo = tokens.PRIMARIA_CLARA if self.selecionado else tokens.CARD

        self.setStyleSheet(f"""
            QFrame {{
                background:{cor_fundo}; border:1.5px solid {cor_borda};
                border-radius:{tokens.RADIUS_SM}px;
            }}
        """)

    def definir_selecionado(self, valor):
        self.selecionado = valor
        self._pintar()

    def mousePressEvent(self, event):
        self.clicado.emit()
        super().mousePressEvent(event)


class LancarFiadoDialog(QDialog):
    """Lançamento manual de uma compra fiada — pensado pra migrar o
    saldo que já existia nas fichas de papel (caderninho tradicional),
    onde a loja quer registrar o valor e os itens sem precisar recriar
    a venda inteira no PDV."""

    def __init__(self, cliente, saldo_atual, parent=None):

        super().__init__(parent)

        self.cliente = cliente
        self._saldo_atual = saldo_atual
        self._tipo_registro = "compra"

        self.setWindowTitle("Lançar Fiado")
        tamanho_fixo_seguro(self, 640, 780)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addLayout(self._construir_cabecalho_dialogo())

        linha_divisoria = QFrame()
        linha_divisoria.setFixedHeight(1)
        linha_divisoria.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        layout.addWidget(linha_divisoria)

        layout.addWidget(self._construir_cartao_cliente())

        layout.addWidget(self._construir_tipo_registro())

        layout.addLayout(self._construir_linha_valor())

        lbl_itens_titulo = QLabel("DESCRIÇÃO (ITENS COMPRADOS)")
        lbl_itens_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.itens = CampoTexto("Ex: mochila, caderno")

        lbl_itens_dica = QLabel(
            'Se preferir, descreva apenas: "Compra anotada no caderno".'
        )
        lbl_itens_dica.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(lbl_itens_titulo)
        layout.addWidget(self.itens)
        layout.addWidget(lbl_itens_dica)

        lbl_data_titulo = QLabel("DATA DA COMPRA")
        lbl_data_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.data = QDateEdit()
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        self.data.setDate(QDate.currentDate())
        # uma compra fiada não pode ser datada no futuro -- sem isso,
        # um clique errado no calendário (ex.: mês seguinte) gera uma
        # "Última Compra" no futuro e "Dias sem comprar" negativo na ficha
        self.data.setMaximumDate(QDate.currentDate())
        self.data.setMinimumHeight(44)
        self.data.setStyleSheet(f"""
            QDateEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
            }}
            QDateEdit:focus {{ border: 1.5px solid {tokens.PRIMARIA}; }}
        """)

        linha_data = QHBoxLayout()
        linha_data.setSpacing(8)
        linha_data.addWidget(self.data, 1)
        linha_data.addWidget(_botao_data_rapida("Hoje", self.data, 0))
        linha_data.addWidget(_botao_data_rapida("Ontem", self.data, -1))

        layout.addWidget(lbl_data_titulo)
        layout.addLayout(linha_data)

        layout.addWidget(self._construir_banner_info(
            "Este lançamento será registrado no histórico do cliente "
            "e será considerado no controle de fiado."
        ))

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar", icone_nome="x")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        self.bt_confirmar = BotaoSucesso("Lançar Fiado", icone_nome="check")
        self.bt_confirmar.setMinimumHeight(46)
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.clicked.connect(self.confirmar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(self.bt_confirmar)

        layout.addLayout(botoes)

        self.valor.setFocus()

    def _construir_cabecalho_dialogo(self):

        linha = QHBoxLayout()
        linha.setSpacing(14)

        icone_circulo = QLabel()
        icone_circulo.setFixedSize(52, 52)
        icone_circulo.setAlignment(Qt.AlignCenter)
        icone_circulo.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; border-radius:26px;
        """)
        icone_circulo.setPixmap(icone_pixmap("shopping-cart", cor=tokens.PRIMARIA, tamanho=22))
        linha.addWidget(icone_circulo)

        col = QVBoxLayout()
        col.setSpacing(2)

        titulo = QLabel("Lançar Fiado")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel("Registra uma compra fiada ou uma dívida anterior do cliente.")
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col.addWidget(titulo)
        col.addWidget(subtitulo)

        linha.addLayout(col, 1)

        bt_fechar = QPushButton()
        bt_fechar.setFixedSize(30, 30)
        bt_fechar.setCursor(Qt.PointingHandCursor)
        bt_fechar.setAutoDefault(False)
        bt_fechar.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        bt_fechar.setToolTip("Fechar")
        bt_fechar.setAccessibleName("Fechar")
        bt_fechar.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        bt_fechar.clicked.connect(self.reject)
        linha.addWidget(bt_fechar, 0, Qt.AlignTop)

        return linha

    def _construir_cartao_cliente(self):

        card = QFrame()
        card.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_MD}px;
        """)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        avatar = Avatar(self.cliente.get("nome", ""), tamanho=44)
        layout.addWidget(avatar)

        col_nome = QVBoxLayout()
        col_nome.setSpacing(4)

        linha_nome = QHBoxLayout()
        linha_nome.setSpacing(8)

        nome = QLabel(self.cliente.get("nome") or "")
        nome.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_MD}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        linha_nome.addWidget(nome)

        ativo = self.cliente.get("ativo", True)
        linha_nome.addWidget(Badge("Ativo" if ativo else "Inativo", "sucesso" if ativo else "erro"))
        linha_nome.addStretch()
        col_nome.addLayout(linha_nome)

        telefone = QLabel(self.cliente.get("telefone") or "Sem telefone")
        telefone.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO};
        """)
        col_nome.addWidget(telefone)

        try:
            movimentos = listar_movimentos_cliente(self.cliente["id"])
            agr = cliente_analise.calcular_agregados(self.cliente, movimentos)
            pontuacao = cliente_analise.calcular_pontuacao(agr)
            emoji_pont, _, texto_pont = pontuacao.partition(" ")
            variante = {
                "🔴": "erro", "🟠": "alerta", "🟡": "alerta",
                "🔵": "info", "🟢": "sucesso",
            }.get(emoji_pont, "neutro")
            col_nome.addWidget(Badge(texto_pont or pontuacao, variante), 0, Qt.AlignLeft)
        except Exception:
            pass

        layout.addLayout(col_nome, 1)

        cor_saldo = tokens.ERRO if self._saldo_atual > 0 else tokens.SECUNDARIA
        layout.addWidget(self._coluna_valor_cliente(
            "Saldo atual", formatar_moeda(self._saldo_atual), cor_saldo
        ))

        limite = self.cliente.get("limite_credito")

        if limite:
            layout.addWidget(self._coluna_valor_cliente(
                "Limite de crédito", formatar_moeda(limite), tokens.TEXTO
            ))
            disponivel = max(0.0, limite - self._saldo_atual)
            layout.addWidget(self._coluna_valor_cliente(
                "Disponível", formatar_moeda(disponivel), tokens.SECUNDARIA
            ))

        return card

    def _coluna_valor_cliente(self, rotulo, valor, cor):

        wrapper = QWidget()
        wrapper.setStyleSheet("background:transparent;")

        col = QVBoxLayout(wrapper)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_SECUNDARIO};
        """)

        lbl_valor = QLabel(valor)
        lbl_valor.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_MD}px;
            font-weight:800; color:{cor};
        """)

        col.addWidget(lbl_rotulo)
        col.addWidget(lbl_valor)

        return wrapper

    def _construir_tipo_registro(self):

        container = QWidget()
        container.setStyleSheet("background:transparent;")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        lbl_titulo = QLabel("O que você deseja registrar?")
        lbl_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:700; color:{tokens.TEXTO};
        """)
        layout.addWidget(lbl_titulo)

        linha = QHBoxLayout()
        linha.setSpacing(10)

        self.cartao_tipo_compra = _OpcaoTipoRegistro(
            "Compra fiada", "Nova compra de produtos"
        )
        self.cartao_tipo_divida = _OpcaoTipoRegistro(
            "Dívida anterior", "Débito que já estava anotado no papel"
        )

        self.cartao_tipo_compra.definir_selecionado(True)
        self.cartao_tipo_compra.clicado.connect(lambda: self._selecionar_tipo_registro("compra"))
        self.cartao_tipo_divida.clicado.connect(lambda: self._selecionar_tipo_registro("divida"))

        linha.addWidget(self.cartao_tipo_compra)
        linha.addWidget(self.cartao_tipo_divida)

        layout.addLayout(linha)

        return container

    def _selecionar_tipo_registro(self, tipo):
        """So' muda a dica do campo Descrição -- não existe diferença
        real no backend entre os dois "tipos" quando lançado por aqui
        (ver docstring de _OpcaoTipoRegistro)."""

        self._tipo_registro = tipo
        self.cartao_tipo_compra.definir_selecionado(tipo == "compra")
        self.cartao_tipo_divida.definir_selecionado(tipo == "divida")

        if tipo == "divida":
            self.itens.setPlaceholderText("Ex: dívida anotada no caderno em janeiro")
        else:
            self.itens.setPlaceholderText("Ex: mochila, caderno")

    def _construir_linha_valor(self):

        linha = QHBoxLayout()
        linha.setSpacing(16)

        col_valor = QVBoxLayout()
        col_valor.setSpacing(6)

        lbl_valor_titulo = QLabel("VALOR DA COMPRA (R$)")
        lbl_valor_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.valor = QLineEdit()
        self.valor.setPlaceholderText("0,00")
        self.valor.setAlignment(Qt.AlignCenter)
        self.valor.setStyleSheet(f"""
            QLineEdit {{
                font-size:30px; font-weight:800; color:{tokens.ERRO};
                border:none; border-bottom:2px solid {tokens.BORDA};
                padding:6px 0; background:transparent;
            }}
        """)
        self.valor.textChanged.connect(self._atualizar_preview_saldo)

        col_valor.addWidget(lbl_valor_titulo)
        col_valor.addWidget(self.valor)

        linha.addLayout(col_valor, 1)
        linha.addWidget(self._construir_preview_saldo(), 1)

        return linha

    def _construir_preview_saldo(self):

        caixa = QFrame()
        caixa.setStyleSheet(f"""
            background:{tokens.SUCESSO_CLARO}; border-radius:{tokens.RADIUS_SM}px;
        """)

        layout = QVBoxLayout(caixa)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        topo = QHBoxLayout()
        topo.setSpacing(6)

        icone_lbl = QLabel()
        icone_lbl.setPixmap(icone_pixmap("bar-chart-2", cor=tokens.SECUNDARIA_HOVER, tamanho=13))
        icone_lbl.setStyleSheet("background:transparent;")
        topo.addWidget(icone_lbl)

        lbl_titulo_preview = QLabel("Saldo após o lançamento")
        lbl_titulo_preview.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.SECUNDARIA_HOVER};
        """)
        topo.addWidget(lbl_titulo_preview)
        topo.addStretch()

        layout.addLayout(topo)

        linha_valores = QHBoxLayout()
        linha_valores.setSpacing(10)

        col_atual = QVBoxLayout()
        col_atual.setSpacing(1)
        lbl_atual_rotulo = QLabel("Saldo atual")
        lbl_atual_rotulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px; color:{tokens.TEXTO_SECUNDARIO};
        """)
        self.lbl_preview_saldo_atual = QLabel(formatar_moeda(self._saldo_atual))
        self.lbl_preview_saldo_atual.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px; font-weight:800; color:{tokens.TEXTO};
        """)
        col_atual.addWidget(lbl_atual_rotulo)
        col_atual.addWidget(self.lbl_preview_saldo_atual)
        linha_valores.addLayout(col_atual)

        seta = QLabel("→")
        seta.setStyleSheet(f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; font-size:16px;")
        linha_valores.addWidget(seta, 0, Qt.AlignVCenter)

        col_novo = QVBoxLayout()
        col_novo.setSpacing(1)
        lbl_novo_rotulo = QLabel("Novo saldo")
        lbl_novo_rotulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px; color:{tokens.TEXTO_SECUNDARIO};
        """)
        self.lbl_preview_novo_saldo = QLabel(formatar_moeda(self._saldo_atual))
        self.lbl_preview_novo_saldo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px; font-weight:800; color:{tokens.SECUNDARIA_HOVER};
        """)
        col_novo.addWidget(lbl_novo_rotulo)
        col_novo.addWidget(self.lbl_preview_novo_saldo)
        linha_valores.addLayout(col_novo)

        layout.addLayout(linha_valores)

        return caixa

    def _atualizar_preview_saldo(self, _texto=None):

        try:
            valor = float((self.valor.text() or "0").replace(",", "."))
        except ValueError:
            valor = 0.0

        novo_saldo = self._saldo_atual + max(0.0, valor)
        self.lbl_preview_novo_saldo.setText(formatar_moeda(novo_saldo))

    def _construir_banner_info(self, texto):

        banner = QFrame()
        banner.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_SM}px;
        """)

        layout = QHBoxLayout(banner)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        icone_lbl = QLabel()
        icone_lbl.setPixmap(icone_pixmap("message-circle", cor=tokens.PRIMARIA_HOVER, tamanho=14))
        icone_lbl.setStyleSheet("background:transparent;")
        layout.addWidget(icone_lbl, 0, Qt.AlignTop)

        lbl = QLabel(texto)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px; color:{tokens.PRIMARIA_HOVER};
        """)
        layout.addWidget(lbl, 1)

        return banner

    def confirmar(self):

        try:
            valor = float(self.valor.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(
                self, "Atenção", "Informe um valor válido."
            )
            return

        if valor <= 0:
            QMessageBox.warning(
                self, "Atenção", "Informe um valor maior que zero."
            )
            return

        itens = self.itens.text().strip() or None

        data_qt = self.data.date()
        data_iso = (
            date(data_qt.year(), data_qt.month(), data_qt.day())
            .isoformat()
            + "T00:00:00"
        )

        self._fiado_pendente = (valor, itens, data_iso)

        limite = self.cliente.get("limite_credito")

        if limite is not None:
            self.bt_confirmar.setEnabled(False)
            rodar_em_thread(
                self,
                saldo_cliente,
                self.cliente["id"],
                ao_sucesso=self._ao_checar_limite_sucesso,
                ao_erro=self._ao_fiado_erro,
                ao_finalizar=self._ao_checar_limite_finalizado,
            )
        else:
            self._enviar_fiado()

    def _ao_checar_limite_finalizado(self):
        self.bt_confirmar.setEnabled(True)

    def _ao_checar_limite_sucesso(self, saldo_atual):

        valor, _itens, _data_iso = self._fiado_pendente
        limite = self.cliente.get("limite_credito")
        saldo_projetado = saldo_atual + valor

        if saldo_projetado > limite:

            resposta = QMessageBox.warning(
                self,
                "Limite de crédito",
                f"Esse lançamento deixa o saldo devedor em "
                f"{formatar_moeda(saldo_projetado)}, acima do limite "
                f"de crédito cadastrado ({formatar_moeda(limite)}).\n\n"
                "Deseja lançar mesmo assim?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if resposta != QMessageBox.Yes:
                return

        self._enviar_fiado()

    def _enviar_fiado(self):

        valor, itens, data_iso = self._fiado_pendente

        self.bt_confirmar.setEnabled(False)

        rodar_em_thread(
            self,
            lancar_fiado_manual,
            self.cliente["id"],
            valor,
            itens,
            data_iso,
            ao_sucesso=self._ao_enviar_fiado_sucesso,
            ao_erro=self._ao_fiado_erro,
            ao_finalizar=self._ao_checar_limite_finalizado,
        )

    def _ao_enviar_fiado_sucesso(self, response):
        if response.status_code in (200, 201):
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_fiado_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))


class RegistrarPagamentoDialog(QDialog):

    def __init__(self, cliente, saldo_devedor, parent=None):

        super().__init__(parent)

        self.cliente = cliente
        self.forma_pagamento = "DINHEIRO"
        self._saldo_devedor = saldo_devedor

        self.setWindowTitle("Registrar Pagamento")
        tamanho_fixo_seguro(self, 640, 760)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addLayout(self._construir_cabecalho_dialogo())

        linha_divisoria = QFrame()
        linha_divisoria.setFixedHeight(1)
        linha_divisoria.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        layout.addWidget(linha_divisoria)

        layout.addWidget(self._construir_cartao_cliente())

        lbl_valor_titulo = QLabel("VALOR A PAGAR (R$)")
        lbl_valor_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(lbl_valor_titulo)

        caixa_valor = QFrame()
        caixa_valor.setStyleSheet(f"""
            QFrame {{
                background: {tokens.FUNDO}; border-radius: {tokens.RADIUS_SM}px;
            }}
        """)
        layout_caixa_valor = QHBoxLayout(caixa_valor)
        layout_caixa_valor.setContentsMargins(14, 4, 8, 4)
        layout_caixa_valor.setSpacing(6)

        lbl_prefixo = QLabel("R$")
        lbl_prefixo.setStyleSheet(f"""
            background:transparent; font-size:18px; font-weight:700;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        layout_caixa_valor.addWidget(lbl_prefixo)

        self.valor = QLineEdit()
        self.valor.setText(formatar_moeda(saldo_devedor, com_simbolo=False))
        self.valor.setAlignment(Qt.AlignRight)
        self.valor.setStyleSheet(f"""
            QLineEdit {{
                font-size:28px; font-weight:800; color:{tokens.SECUNDARIA};
                border:none; padding:8px 0; background:transparent;
            }}
        """)
        layout_caixa_valor.addWidget(self.valor, 1)

        bt_valor_total = QPushButton()
        bt_valor_total.setFixedSize(34, 34)
        bt_valor_total.setCursor(Qt.PointingHandCursor)
        bt_valor_total.setAutoDefault(False)
        bt_valor_total.setToolTip("Preencher com o saldo devedor inteiro")
        bt_valor_total.setAccessibleName("Preencher com o saldo devedor inteiro")
        bt_valor_total.setIcon(icone("refresh-cw", cor=tokens.TEXTO_TERCIARIO, tamanho=15))
        bt_valor_total.setStyleSheet(f"""
            QPushButton {{ background:{tokens.CARD}; border:none; border-radius:{tokens.RADIUS_SM}px; }}
            QPushButton:hover {{ background:{tokens.BORDA}; }}
        """)
        bt_valor_total.clicked.connect(
            lambda: self.valor.setText(formatar_moeda(self._saldo_devedor, com_simbolo=False))
        )
        layout_caixa_valor.addWidget(bt_valor_total)

        layout.addWidget(caixa_valor)

        lbl_saldo_dica = QLabel(f"Saldo devedor: {formatar_moeda(saldo_devedor)}")
        lbl_saldo_dica.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(lbl_saldo_dica)

        lbl_forma_titulo = QLabel("FORMA DE PAGAMENTO")
        lbl_forma_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(lbl_forma_titulo)

        formas_layout = QGridLayout()
        formas_layout.setSpacing(8)

        self.botoes_forma = {}

        for indice, (rotulo, valor) in enumerate(FORMAS_PAGAMENTO):

            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setAutoDefault(False)
            bt.setMinimumHeight(46)
            bt.setIcon(icone(
                _ICONES_FORMA_PAGAMENTO.get(valor, "dollar-sign"),
                cor=tokens.TEXTO, tamanho=15,
            ))
            bt.clicked.connect(
                lambda checked, v=valor: self.selecionar_forma(v)
            )

            self.botoes_forma[valor] = bt
            formas_layout.addWidget(bt, indice // 3, indice % 3)

        layout.addLayout(formas_layout)

        lbl_obs_titulo = QLabel("OBSERVAÇÃO (OPCIONAL)")
        lbl_obs_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.observacao = CampoTexto("Ex: pagamento parcial, combinado...")

        layout.addWidget(lbl_obs_titulo)
        layout.addWidget(self.observacao)

        lbl_data_titulo = QLabel("DATA DO PAGAMENTO")
        lbl_data_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        linha_data = QHBoxLayout()
        linha_data.setSpacing(8)

        self.data = QDateEdit()
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        self.data.setDate(QDate.currentDate())
        # mesmo motivo do LancarFiadoDialog: pagamento no futuro não
        # existe, e gerava "Dias sem comprar" negativo na ficha
        self.data.setMaximumDate(QDate.currentDate())
        self.data.setMinimumHeight(44)
        self.data.setStyleSheet(f"""
            QDateEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
            }}
            QDateEdit:focus {{ border: 1.5px solid {tokens.SECUNDARIA}; }}
        """)
        linha_data.addWidget(self.data, 1)

        # atalho de um clique pra "hoje"/"ontem" -- evita abrir o
        # calendário toda vez pra um pagamento que quase sempre é feito
        # na hora (pedido direto: "colocar a data mais rápido")
        bt_hoje = _botao_data_rapida("Hoje", self.data, 0)
        bt_ontem = _botao_data_rapida("Ontem", self.data, -1)
        linha_data.addWidget(bt_hoje)
        linha_data.addWidget(bt_ontem)

        layout.addWidget(lbl_data_titulo)
        layout.addLayout(linha_data)

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar", icone_nome="x")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        self.bt_confirmar = BotaoSucesso("Confirmar Pagamento", icone_nome="check")
        self.bt_confirmar.setMinimumHeight(46)
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.clicked.connect(self.confirmar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(self.bt_confirmar)

        layout.addLayout(botoes)

        self.selecionar_forma("DINHEIRO")
        self.valor.setFocus()
        self.valor.selectAll()

    def _construir_cabecalho_dialogo(self):

        linha = QHBoxLayout()
        linha.setSpacing(14)

        icone_circulo = QLabel()
        icone_circulo.setFixedSize(52, 52)
        icone_circulo.setAlignment(Qt.AlignCenter)
        icone_circulo.setStyleSheet(f"""
            background:{tokens.SUCESSO_CLARO}; border-radius:26px;
        """)
        icone_circulo.setPixmap(icone_pixmap("dollar-sign", cor=tokens.SECUNDARIA_HOVER, tamanho=22))
        linha.addWidget(icone_circulo)

        col = QVBoxLayout()
        col.setSpacing(2)

        titulo = QLabel("Registrar Pagamento")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel("Registra um pagamento do cliente no sistema.")
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col.addWidget(titulo)
        col.addWidget(subtitulo)

        linha.addLayout(col, 1)

        bt_fechar = QPushButton()
        bt_fechar.setFixedSize(30, 30)
        bt_fechar.setCursor(Qt.PointingHandCursor)
        bt_fechar.setAutoDefault(False)
        bt_fechar.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        bt_fechar.setToolTip("Fechar")
        bt_fechar.setAccessibleName("Fechar")
        bt_fechar.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        bt_fechar.clicked.connect(self.reject)
        linha.addWidget(bt_fechar, 0, Qt.AlignTop)

        return linha

    def _construir_cartao_cliente(self):

        card = QFrame()
        card.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_MD}px;
        """)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        avatar = Avatar(self.cliente.get("nome", ""), tamanho=44)
        layout.addWidget(avatar)

        col_nome = QVBoxLayout()
        col_nome.setSpacing(4)

        nome = QLabel(self.cliente.get("nome") or "")
        nome.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_MD}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        col_nome.addWidget(nome)

        telefone = QLabel(self.cliente.get("telefone") or "Sem telefone")
        telefone.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO};
        """)
        col_nome.addWidget(telefone)

        try:
            movimentos = listar_movimentos_cliente(self.cliente["id"])
            agr = cliente_analise.calcular_agregados(self.cliente, movimentos)
            pontuacao = cliente_analise.calcular_pontuacao(agr)
            emoji_pont, _, texto_pont = pontuacao.partition(" ")
            variante = {
                "🔴": "erro", "🟠": "alerta", "🟡": "alerta",
                "🔵": "info", "🟢": "sucesso",
            }.get(emoji_pont, "neutro")
            col_nome.addWidget(Badge(texto_pont or pontuacao, variante), 0, Qt.AlignLeft)
            total_comprado = agr["total_comprado"]
        except Exception:
            total_comprado = None

        layout.addLayout(col_nome, 1)

        col_saldo = QVBoxLayout()
        col_saldo.setSpacing(2)
        lbl_saldo_rotulo = QLabel("Saldo devedor")
        lbl_saldo_rotulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px; color:{tokens.TEXTO_SECUNDARIO};
        """)
        lbl_saldo_valor = QLabel(formatar_moeda(self._saldo_devedor))
        lbl_saldo_valor.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_MD}px; font-weight:800; color:{tokens.ERRO};
        """)
        col_saldo.addWidget(lbl_saldo_rotulo)
        col_saldo.addWidget(lbl_saldo_valor)

        if total_comprado is not None:
            lbl_total = QLabel(f"Total de compras: {formatar_moeda(total_comprado)}")
            lbl_total.setStyleSheet(f"""
                background:transparent; font-size:{tokens.TAMANHO_XS}px; color:{tokens.TEXTO_TERCIARIO};
            """)
            col_saldo.addWidget(lbl_total)

        layout.addLayout(col_saldo)

        return card

    def selecionar_forma(self, valor):

        self.forma_pagamento = valor

        for chave, botao in self.botoes_forma.items():

            selecionado = chave == valor

            botao.setChecked(selecionado)
            botao.setIcon(icone(
                _ICONES_FORMA_PAGAMENTO.get(chave, "dollar-sign"),
                cor=tokens.TEXTO_CLARO if selecionado else tokens.TEXTO,
                tamanho=15,
            ))

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.SECUNDARIA if selecionado else tokens.FUNDO};
                    color: {tokens.TEXTO_CLARO if selecionado else tokens.TEXTO};
                    border-radius: {tokens.RADIUS_SM}px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background: {tokens.SECUNDARIA_HOVER if selecionado else tokens.BORDA};
                }}
            """)

    def confirmar(self):

        try:
            valor = float(self.valor.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(
                self, "Atenção", "Informe um valor válido."
            )
            return

        if valor <= 0:
            QMessageBox.warning(
                self, "Atenção", "Informe um valor maior que zero."
            )
            return

        data_qt = self.data.date()
        data_iso = (
            date(data_qt.year(), data_qt.month(), data_qt.day())
            .isoformat()
            + "T00:00:00"
        )

        self._pagamento_valor_pendente = valor
        self.bt_confirmar.setEnabled(False)

        rodar_em_thread(
            self,
            registrar_pagamento,
            self.cliente["id"],
            valor,
            self.forma_pagamento,
            descricao=self.observacao.text().strip() or None,
            data=data_iso,
            ao_sucesso=self._ao_registrar_pagamento_sucesso,
            ao_erro=self._ao_pagamento_erro,
            ao_finalizar=self._ao_registrar_pagamento_finalizado,
        )

    def _ao_registrar_pagamento_finalizado(self):
        self.bt_confirmar.setEnabled(True)

    def _ao_pagamento_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_registrar_pagamento_sucesso(self, response):

        if response.status_code not in (200, 201):
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))
            return

        # o recibo NAO sai mais sozinho -- só imprime se o usuário
        # pedir aqui, na hora (pedido direto: tava saindo automático
        # demais, sem perguntar nada).
        resposta = QMessageBox.question(
            self,
            "Pagamento Registrado",
            "Pagamento registrado com sucesso!\n\n"
            "Deseja imprimir o recibo de pagamento?",
        )

        if resposta == QMessageBox.Yes:
            self._imprimir_recibo_pagamento(self._pagamento_valor_pendente)

        self.accept()

    # ======================================
    # RECIBO DE PAGAMENTO -- só é impresso se o usuário confirmar
    # depois de registrar o pagamento (ver confirmar() acima), mesmo
    # padrão de impressora térmica com fallback pro diálogo normal do
    # Windows usado no extrato de fechamento de caixa (ver
    # telas/fechar_caixa.py).
    # ======================================

    def _imprimir_recibo_pagamento(self, valor):

        # a data escolhida no dialogo (Hoje/Ontem) nao tem hora -- usa
        # o horario atual (momento em que o recibo esta sendo gerado)
        # junto com o dia selecionado, pra nao imprimir "as 00:00"
        data_qt = self.data.date()
        agora = datetime.now()
        momento = datetime(
            data_qt.year(), data_qt.month(), data_qt.day(),
            agora.hour, agora.minute,
        ).isoformat()

        rodar_em_thread(
            self,
            _buscar_dados_recibo_pagamento,
            self.cliente["id"],
            valor,
            momento,
            ao_sucesso=self._ao_dados_recibo_sucesso,
            ao_erro=self._ao_pagamento_erro,
        )

    def _ao_dados_recibo_sucesso(self, resultado):

        saldo_depois, responsavel, config_loja, valor, momento = resultado

        config_impressora = preferencias_service.carregar_impressora_termica()

        if config_impressora and config_impressora.get("ativa"):

            ok, erro = impressora_termica_service.imprimir_recibo_pagamento(
                self.cliente.get("nome", ""),
                valor,
                self.forma_pagamento,
                self._saldo_devedor,
                saldo_depois,
                responsavel,
                momento,
                config_loja,
                config_impressora,
            )

            if ok:
                return

            resposta = QMessageBox.question(
                self,
                "Falha na impressora térmica",
                f"{erro}\n\nQuer tentar imprimir pela janela normal do Windows?",
            )

            if resposta != QMessageBox.Yes:
                return

        html = self._montar_html_recibo_pagamento(
            valor, saldo_depois, responsavel, momento, config_loja
        )
        comprovante_service.imprimir(html, self)

    def _montar_html_recibo_pagamento(
        self, valor, saldo_depois, responsavel, momento, config_loja
    ):

        nome_loja = config_loja.get("nome_loja") or "Vertex ERP"
        telefone_loja = config_loja.get("telefone") or ""

        data_texto = datetime.fromisoformat(momento).strftime("%d/%m/%Y às %H:%M")

        quitado = saldo_depois <= 0.009
        situacao_texto = "Quitado" if quitado else "Saldo em aberto"
        cor_situacao = "#16A34A" if quitado else "#DC2626"

        return f"""
        <div style="text-align:center;">
            <h2 style="margin-bottom:0;">{nome_loja}</h2>
            {f"<div style='color:#666;'>WhatsApp: {telefone_loja}</div>" if telefone_loja else ""}
        </div>
        <hr>
        <h3 style="text-align:center; margin:8px 0;">RECIBO DE PAGAMENTO</h3>
        <hr>
        <table width="100%" cellspacing="4">
            <tr><td><b>Cliente:</b></td><td>{self.cliente.get('nome', '')}</td></tr>
            <tr><td><b>Data:</b></td><td>{data_texto}</td></tr>
            <tr><td><b>Atendente:</b></td><td>{responsavel}</td></tr>
        </table>
        <h4 style="margin:14px 0 4px;">PAGAMENTO RECEBIDO</h4>
        <table width="100%" cellspacing="4">
            <tr><td>Forma de pagamento:</td><td align="right">{self.forma_pagamento}</td></tr>
            <tr><td>Valor recebido:</td>
                <td align="right"><b>{formatar_moeda(valor)}</b></td></tr>
        </table>
        <h4 style="margin:14px 0 4px;">RESUMO DO CADASTRO</h4>
        <table width="100%" cellspacing="4">
            <tr><td>Saldo antes do pagamento:</td>
                <td align="right">{formatar_moeda(self._saldo_devedor)}</td></tr>
            <tr><td>Pagamento registrado:</td>
                <td align="right">-{formatar_moeda(valor)}</td></tr>
            <tr><td><b>Saldo atual:</b></td>
                <td align="right"><b>{formatar_moeda(saldo_depois)}</b></td></tr>
        </table>
        <p style="margin-top:8px;">
            Situação:
            <span style="color:{cor_situacao}; font-weight:bold;">
                {situacao_texto}
            </span>
        </p>
        <hr>
        <p style="text-align:center;">Obrigado pelo pagamento e pela preferência!</p>
        <p style="color:#94A3B8; font-size:8pt; text-align:center;">
            Este comprovante não possui valor fiscal.
        </p>
        """


class LancarHaverDialog(QDialog):
    """Crédito manual em favor do cliente (desconto, devolução,
    cortesia) -- reduz o saldo devedor igual um pagamento, mas nunca é
    dinheiro recebido de verdade, então nunca mexe no caixa."""

    def __init__(self, cliente, saldo_devedor, parent=None):

        super().__init__(parent)

        self.cliente = cliente

        self.setWindowTitle("Lançar Haver")
        tamanho_fixo_seguro(self, 420, 420)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        titulo = QLabel("Lançar Haver")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            f"Crédito em favor de {cliente['nome']} (desconto, devolução, "
            f"cortesia). Saldo devedor atual: {formatar_moeda(saldo_devedor)}."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(6)

        lbl_valor_titulo = QLabel("VALOR DO CRÉDITO (R$)")
        lbl_valor_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.valor = QLineEdit()
        self.valor.setPlaceholderText("0,00")
        self.valor.setAlignment(Qt.AlignCenter)
        self.valor.setStyleSheet(f"""
            QLineEdit {{
                font-size:32px; font-weight:800; color:{tokens.ALERTA};
                border:none; border-bottom:2px solid {tokens.BORDA};
                padding:6px 0; background:transparent;
            }}
        """)

        layout.addWidget(lbl_valor_titulo)
        layout.addWidget(self.valor)

        lbl_desc_titulo = QLabel("MOTIVO")
        lbl_desc_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.descricao = CampoTexto("Ex: desconto combinado, devolução de item")

        layout.addWidget(lbl_desc_titulo)
        layout.addWidget(self.descricao)

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        self.bt_confirmar = BotaoPrimario("Salvar")
        self.bt_confirmar.setMinimumHeight(46)
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.clicked.connect(self.confirmar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(self.bt_confirmar)

        layout.addLayout(botoes)

        self.valor.setFocus()

    def confirmar(self):

        try:
            valor = float(self.valor.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(self, "Atenção", "Informe um valor válido.")
            return

        if valor <= 0:
            QMessageBox.warning(
                self, "Atenção", "Informe um valor maior que zero."
            )
            return

        self.bt_confirmar.setEnabled(False)

        rodar_em_thread(
            self,
            lancar_haver,
            self.cliente["id"],
            valor,
            self.descricao.text().strip() or "Haver",
            ao_sucesso=self._ao_confirmar_sucesso,
            ao_erro=self._ao_confirmar_erro,
            ao_finalizar=self._ao_confirmar_finalizado,
        )

    def _ao_confirmar_finalizado(self):
        self.bt_confirmar.setEnabled(True)

    def _ao_confirmar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_confirmar_sucesso(self, response):

        if response.status_code in (200, 201):
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))


class FichaClienteDialog(QDialog):

    _TIMELINE_PAGINA = 30  # scroll incremental: 30 lançamentos por vez

    def __init__(self, cliente, parent=None):

        super().__init__(parent)

        self.cliente = cliente
        self._vendas_por_id = {}
        self._nomes_produto = {}
        self._movimentos = []
        self._carregando = False

        self._filtro_timeline = "TODOS"
        self._busca_timeline = ""
        self._timeline_qtd_exibida = self._TIMELINE_PAGINA

        self.setWindowTitle(f"Ficha - {cliente['nome']}")
        self._dimensionar_e_centralizar()
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        raiz.addWidget(self._construir_cabecalho())

        corpo = QHBoxLayout()
        corpo.setContentsMargins(24, 16, 24, 12)
        corpo.setSpacing(16)

        coluna_esquerda = QVBoxLayout()
        coluna_esquerda.setSpacing(12)

        coluna_esquerda.addWidget(self._construir_linha_cards())
        coluna_esquerda.addLayout(self._construir_botoes_acao())
        coluna_esquerda.addLayout(self._construir_filtros_timeline())
        coluna_esquerda.addWidget(self._construir_timeline(), stretch=1)

        corpo.addLayout(coluna_esquerda, stretch=2)
        corpo.addWidget(self._construir_painel_lateral())

        raiz.addLayout(corpo, stretch=1)
        raiz.addWidget(self._construir_rodape())

        self.carregar()

    def _dimensionar_e_centralizar(self):
        """Tamanho da janela calculado a partir da tela de verdade (90%
        da área útil, sem contar a barra de tarefas), nunca um valor
        fixo no código -- funciona igual em qualquer resolução (de
        1366x768 até 4K), sempre dentro da área disponível do Windows,
        e já abre centralizada."""

        tela = QApplication.primaryScreen().availableGeometry()

        largura = int(tela.width() * 0.9)
        altura = int(tela.height() * 0.9)

        self.resize(largura, altura)
        self.move(
            tela.x() + (tela.width() - largura) // 2,
            tela.y() + (tela.height() - altura) // 2,
        )

    # ======================================
    # CONSTRUÇÃO DA INTERFACE
    # ======================================

    def _construir_cabecalho(self):
        """Cabeçalho compacto (~40% mais baixo que o anterior): só
        avatar, nome, telefone, status e os botões de contato -- o
        resto (CPF/CNPJ, endereço, estatísticas) virou mini-card ou
        painel lateral, não ocupa mais altura fixa aqui em cima."""

        cabecalho = QFrame()
        cabecalho.setStyleSheet(f"background:{tokens.SIDEBAR};")

        layout = QHBoxLayout(cabecalho)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(14)

        self.avatar = Avatar(self.cliente.get("nome", ""), tamanho=40)
        layout.addWidget(self.avatar)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(1)

        linha_nome = QHBoxLayout()
        linha_nome.setSpacing(10)

        self.lbl_titulo = QLabel(self.cliente["nome"])
        self.lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_CLARO};
            font-size:{tokens.TAMANHO_LG}px; font-weight:800;
        """)

        self.badge_ativo = Badge("Ativo", "sucesso")

        # selo de pontuacao (Cliente Ocasional/Frequente/Excelente/...)
        # -- comeca vazio, so' ganha texto/cor em _atualizar_stats
        # (precisa do historico de movimentos, que ainda nao foi
        # buscado nesse ponto da construcao)
        self.badge_pontuacao = Badge("", "info")
        self.badge_pontuacao.setVisible(False)

        linha_nome.addWidget(self.lbl_titulo)
        linha_nome.addWidget(self.badge_ativo, 0)
        linha_nome.addWidget(self.badge_pontuacao, 0)
        linha_nome.addStretch()

        self.lbl_subtitulo = QLabel()
        self.lbl_subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_texto.addLayout(linha_nome)
        col_texto.addWidget(self.lbl_subtitulo)

        layout.addLayout(col_texto, stretch=1)

        linha_contato = QHBoxLayout()
        linha_contato.setSpacing(8)

        self.bt_whatsapp = self._botao_contato("WhatsApp ▾", None)
        self.menu_whatsapp = self._construir_menu_whatsapp()
        self.bt_whatsapp.setMenu(self.menu_whatsapp)

        self.bt_ligar = self._botao_contato("Ligar", self.abrir_ligacao)
        self.bt_email = self._botao_contato("E-mail", self.abrir_email)

        linha_contato.addWidget(self.bt_whatsapp)
        linha_contato.addWidget(self.bt_ligar)
        linha_contato.addWidget(self.bt_email)

        divisor_cabecalho = QFrame()
        divisor_cabecalho.setFixedSize(1, 24)
        divisor_cabecalho.setStyleSheet("background: rgba(255,255,255,0.16);")
        linha_contato.addWidget(divisor_cabecalho)

        self.bt_editar_cabecalho = QPushButton("Editar Cliente")
        self.bt_editar_cabecalho.setIcon(icone("edit-2", cor="white", tamanho=14))
        self.bt_editar_cabecalho.setCursor(Qt.PointingHandCursor)
        self.bt_editar_cabecalho.setFixedHeight(30)
        self.bt_editar_cabecalho.setAutoDefault(False)
        self.bt_editar_cabecalho.clicked.connect(self.editar_cliente)
        self.bt_editar_cabecalho.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: white;
                border: 1.5px solid rgba(255,255,255,0.5);
                border-radius: {tokens.RADIUS_SM}px;
                font-size: {tokens.TAMANHO_XS}px;
                font-weight: 700;
                padding: 0 14px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.12); }}
        """)
        linha_contato.addWidget(self.bt_editar_cabecalho)

        layout.addLayout(linha_contato)

        self._atualizar_cabecalho(self.cliente)
        self._atualizar_avatar(self.cliente)

        return cabecalho

    def _construir_menu_whatsapp(self):
        """O botão WhatsApp do cabeçalho virou um menu com as ações
        mais usadas -- antes eram vários botões espalhados (inclusive
        "Enviar Último Comprovante", que morava na barra de ações)."""

        menu = QMenu(self)

        menu.addAction("Enviar Último Comprovante", self.enviar_ultimo_comprovante)
        menu.addAction("Enviar Extrato Completo", self.enviar_extrato_whatsapp)
        menu.addAction("Enviar Cobrança", self.enviar_cobranca_whatsapp)

        return menu

    def _botao_contato(self, texto, callback):
        """Botão de contato rápido só com texto (sem ícone) — os ícones
        'phone'/'map-pin' não existem no pacote Lucide já baixado, e a
        decisão foi não baixar novos ícones pra isso. Estilo "vidro"
        sobre o fundo escuro do cabeçalho, já que o BotaoSecundario
        padrão foi desenhado pra fundo claro."""

        botao = QPushButton(texto)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setFixedHeight(28)
        if callback:
            botao.clicked.connect(callback)
        botao.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.08);
                color: {tokens.TEXTO_SIDEBAR};
                border: 1px solid rgba(255,255,255,0.18);
                border-radius: {tokens.RADIUS_SM}px;
                font-size: {tokens.TAMANHO_XS}px;
                font-weight: 600;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.16);
            }}
            QPushButton:disabled {{
                color: {tokens.TEXTO_SIDEBAR_APAGADO};
                border-color: rgba(255,255,255,0.08);
            }}
        """)
        return botao

    def _telefone_digitos(self):
        return "".join(c for c in (self.cliente.get("telefone") or "") if c.isdigit())

    def abrir_ligacao(self):

        digitos = self._telefone_digitos()

        if digitos:
            QDesktopServices.openUrl(QUrl(f"tel:{digitos}"))

    def abrir_email(self):

        email = self.cliente.get("email")

        if email:
            QDesktopServices.openUrl(QUrl(f"mailto:{email}"))


    # tamanho fixo e uniforme pra cada mini-card -- é o que permite o
    # FlowLayout calcular a quebra de linha sozinho (ver design/widgets.py)
    # sem depender de "stretch"; nesses valores, 5 cards cabem numa
    # linha só na largura padrão do diálogo (ver __init__: resize),
    # e quebra sozinho pra mais linhas se a janela ficar mais estreita.
    _LARGURA_MINI_CARD = 140
    _ALTURA_MINI_CARD = 56

    def _construir_linha_cards(self):
        """Indicadores em grid responsivo -- 2 FlowLayouts separados
        (um por linha), não um só compartilhado: um FlowLayout único
        deixava um 6º card "subir" pra 1ª linha em janelas bem largas
        (maximizada, por exemplo), quebrando o agrupamento pedido
        (1ª linha = financeiro do dia a dia, 2ª linha = perfil do
        cliente). Com um FlowLayout por linha, cada grupo de 5 fica
        sempre junto, em qualquer largura -- só quebra pra uma 3ª/4ª
        linha se a própria linha não couber inteira (janela estreita)."""

        container = QFrame()
        container.setStyleSheet("background:transparent;")

        layout_externo = QVBoxLayout(container)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        layout_externo.setSpacing(8)

        linha1 = FlowLayout(espaco_h=8, espaco_v=8)
        linha2 = FlowLayout(espaco_h=8, espaco_v=8)

        # linha 1 -- financeiro do dia a dia
        self.lbl_saldo_valor = self._mini_card(linha1, "SALDO ATUAL", "dollar-sign", tokens.ERRO)
        self.lbl_total_comprado = self._mini_card(linha1, "TOTAL COMPRADO", "shopping-cart", tokens.PRIMARIA)
        self.lbl_total_pago_card = self._mini_card(linha1, "TOTAL PAGO", "dollar-sign", tokens.SECUNDARIA)
        self.lbl_ultima_compra = self._mini_card(linha1, "ÚLTIMA COMPRA", "calendar", tokens.PRIMARIA)
        self.lbl_ultimo_pagamento = self._mini_card(linha1, "ÚLTIMO PAGAMENTO", "calendar", tokens.PRIMARIA)

        # linha 2 -- perfil/relacionamento do cliente
        self.lbl_cliente_desde = self._mini_card(linha2, "CLIENTE DESDE", "calendar", tokens.PRIMARIA)
        self.lbl_status_financeiro = self._mini_card(linha2, "STATUS FINANCEIRO", "bar-chart-2", tokens.PRIMARIA)
        self.lbl_score = self._mini_card(linha2, "PONTUAÇÃO", "trending-up", tokens.PRIMARIA)
        self.lbl_dias_desde_ultima_compra = self._mini_card(linha2, "DIAS SEM COMPRAR", "calendar", tokens.ALERTA)
        self.lbl_limite_credito = self._mini_card(linha2, "LIMITE DE CRÉDITO", "credit-card", tokens.PRIMARIA)

        layout_externo.addLayout(linha1)
        layout_externo.addLayout(linha2)

        self.lbl_aviso_status = QLabel("")
        self.lbl_aviso_status.setAlignment(Qt.AlignCenter)
        self.lbl_aviso_status.setWordWrap(True)
        layout_externo.addWidget(self.lbl_aviso_status)

        return container

    def _mini_card(self, layout, titulo, icone_nome=None, cor=None):

        cor = cor or tokens.PRIMARIA

        card = QFrame()
        card.setFixedSize(self._LARGURA_MINI_CARD, self._ALTURA_MINI_CARD)
        card.setStyleSheet(f"""
            background:{tokens.CARD}; border:1px solid {tokens.BORDA};
            border-radius:{tokens.RADIUS_SM}px;
        """)

        linha = QHBoxLayout(card)
        linha.setContentsMargins(8, 6, 10, 6)
        linha.setSpacing(8)

        if icone_nome:

            cor_rgb = QColor(cor)
            badge_icone = QLabel()
            badge_icone.setFixedSize(26, 26)
            badge_icone.setAlignment(Qt.AlignCenter)
            badge_icone.setStyleSheet(f"""
                background: rgba({cor_rgb.red()}, {cor_rgb.green()}, {cor_rgb.blue()}, 0.12);
                border:none; border-radius: {tokens.RADIUS_SM}px;
            """)
            badge_icone.setPixmap(icone_pixmap(icone_nome, cor=cor, tamanho=13))
            linha.addWidget(badge_icone)

        col = QVBoxLayout()
        col.setSpacing(2)

        # título numa linha só (sem quebra) -- todos os rótulos usados
        # cabem tranquilos na largura do card nesse tamanho de fonte
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setWordWrap(False)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; border:none; font-size:8px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        # valor pode quebrar linha (alguns são mais longos, ex.
        # pontuação/status), mas a altura fixa do card garante que a
        # linha toda continua com a mesma altura mesmo assim
        lbl_valor = QLabel("—")
        lbl_valor.setWordWrap(True)
        lbl_valor.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        col.addWidget(lbl_titulo)
        col.addWidget(lbl_valor, stretch=1)

        linha.addLayout(col, 1)

        layout.addWidget(card)

        return lbl_valor

    def _construir_botoes_acao(self):
        """FlowLayout em vez de QHBoxLayout -- uma linha fixa de 5
        botões força a largura mínima do diálogo inteiro à soma de
        todos eles (o que impedia a janela de encolher); com o
        FlowLayout, a largura mínima vira só a do maior botão sozinho,
        e os outros quebram pra linha de baixo se não couberem."""

        layout = FlowLayout(espaco_h=10, espaco_v=10)

        self.bt_lancar_fiado = BotaoPerigo("Lançar Fiado", icone_nome="plus")
        self.bt_lancar_fiado.setMinimumHeight(46)
        self.bt_lancar_fiado.setAutoDefault(False)
        self.bt_lancar_fiado.clicked.connect(self.lancar_fiado)

        self.bt_pagar = BotaoSucesso("Registrar Pagamento", icone_nome="check")
        self.bt_pagar.setMinimumHeight(46)
        self.bt_pagar.setAutoDefault(False)
        self.bt_pagar.clicked.connect(self.registrar_pagamento)

        self.bt_haver = BotaoSecundario("Lançar Haver", icone_nome="gift")
        self.bt_haver.setMinimumHeight(46)
        self.bt_haver.setAutoDefault(False)
        self.bt_haver.clicked.connect(self.lancar_haver)

        self.bt_extrato = BotaoSecundario("Imprimir Extrato", icone_nome="printer")
        self.bt_extrato.setMinimumHeight(46)
        self.bt_extrato.setAutoDefault(False)
        self.bt_extrato.clicked.connect(self.imprimir_extrato)

        self.bt_csv = BotaoSecundario("Exportar CSV", icone_nome="download")
        self.bt_csv.setMinimumHeight(46)
        self.bt_csv.setAutoDefault(False)
        self.bt_csv.clicked.connect(self.exportar_csv)

        layout.addWidget(self.bt_lancar_fiado)
        layout.addWidget(self.bt_pagar)
        layout.addWidget(self.bt_haver)
        layout.addWidget(self.bt_extrato)
        layout.addWidget(self.bt_csv)

        return layout

    def enviar_ultimo_comprovante(self):
        """Manda um texto pronto com os dados da venda (não mais o PDF
        anexado) -- mesmo padrão de mensagem de texto direta usado nas
        outras duas opções do menu WhatsApp."""

        vendas_cliente = [
            v for v in listar_vendas()
            if v.get("cliente_id") == self.cliente["id"]
        ]

        if not vendas_cliente:
            QMessageBox.information(
                self,
                "Sem compras",
                "Este cliente ainda não tem nenhuma compra registrada.",
            )
            return

        ultima_venda = max(vendas_cliente, key=lambda v: v["data"])

        dados = comprovante_service.buscar_dados_comprovante(ultima_venda["id"])

        if not dados:
            QMessageBox.critical(
                self, "Erro", "Não foi possível carregar os dados da venda."
            )
            return

        data = str(dados.get("data", "")).replace("T", " ")[:16]

        resposta = QMessageBox.question(
            self,
            "Enviar Último Comprovante",
            f"Enviar pelo WhatsApp o comprovante da venda #{dados['venda_id']}"
            f" ({data}, {formatar_moeda(dados['valor_total'])})?",
        )

        if resposta != QMessageBox.Yes:
            return

        nome_loja = api.configuracoes().get("nome_loja") or "Vertex ERP"

        itens_texto = "\n".join(
            f"{item['quantidade']}x {item['nome']} — "
            f"{formatar_moeda(item['subtotal'])}"
            for item in dados.get("itens", [])
        ) or "—"

        if dados.get("forma_pagamento_2"):
            valor_principal = float(dados["valor_total"]) - float(
                dados.get("valor_forma_2") or 0
            )
            pagamento_texto = (
                f"{formatar_moeda(valor_principal)} ({dados['forma_pagamento']}) + "
                f"{formatar_moeda(dados['valor_forma_2'])} ({dados['forma_pagamento_2']})"
            )
        else:
            pagamento_texto = dados.get("forma_pagamento") or "—"

        situacao_texto = (
            "EM ABERTO" if (dados.get("situacao") or "PAGO") == "FIADO" else "PAGO"
        )

        texto = (
            f"Olá, {self.cliente.get('nome', '')}! Tudo bem?\n\n"
            f"Agradecemos pela sua compra na {nome_loja}.\n\n"
            f"COMPROVANTE DE VENDA\n\n"
            f"Data: {data}\n"
            f"Venda nº: {dados['venda_id']}\n\n"
            f"Itens:\n"
            f"{itens_texto}\n\n"
            f"Valor total: {formatar_moeda(dados['valor_total'])}\n"
            f"Forma de pagamento: {pagamento_texto}\n"
            f"Situação: {situacao_texto}\n\n"
            f"Agradecemos pela preferência. Qualquer dúvida, estamos à "
            f"disposição!\n\n"
            f"Equipe {nome_loja}"
        )

        self._enviar_texto_whatsapp(texto, "Enviar Último Comprovante")

    # ======================================
    # MENU "WHATSAPP ▾" -- mensagens de texto livre (extrato, cobrança,
    # saldo, haver, cadastro). Diferente do comprovante (que anexa um
    # PDF), aqui é só texto -- mesmo esquema de fallback manual (abrir
    # o wa.me com a mensagem pronta) usado em comprovante_acoes.py.
    # ======================================

    def _enviar_texto_whatsapp(self, texto, titulo="WhatsApp"):

        telefone = self.cliente.get("telefone")

        if not telefone:
            QMessageBox.warning(
                self,
                "Sem telefone",
                "Este cliente não tem telefone cadastrado.\n\n"
                "Cadastre um telefone na ficha do cliente pra poder "
                "enviar mensagens automaticamente.",
            )
            return

        config = api.configuracoes()

        if not config.get("whatsapp_ativo"):
            self._abrir_fallback_whatsapp(telefone, texto)
            return

        response = enviar_whatsapp_texto(self.cliente["id"], texto)

        if response.status_code == 200:
            QMessageBox.information(
                self, titulo, "Mensagem enviada pelo WhatsApp com sucesso."
            )
            return

        try:
            erro = response.json().get("detail") or response.text
        except Exception:
            erro = response.text

        resposta = QMessageBox.question(
            self,
            "Falha no envio automático",
            f"Não consegui enviar automaticamente:\n\n{erro}\n\n"
            "Quer abrir o WhatsApp manualmente com a mensagem pronta?",
        )

        if resposta == QMessageBox.Yes:
            self._abrir_fallback_whatsapp(telefone, texto)

    def _abrir_fallback_whatsapp(self, telefone, texto):

        digitos = "".join(c for c in telefone if c.isdigit())

        if len(digitos) <= 11:
            digitos = "55" + digitos

        QDesktopServices.openUrl(
            QUrl(f"https://wa.me/{digitos}?text={quote(texto)}")
        )

    def enviar_extrato_whatsapp(self):
        """'Extrato Completo' -- resumo financeiro curto (total
        comprado, total pago, saldo em aberto), não mais o extrato
        movimento a movimento -- mensagem mais direta pro WhatsApp."""

        saldo = saldo_cliente(self.cliente["id"])

        agr = cliente_analise.calcular_agregados(
            self.cliente, [mov for mov, _ in reversed(self._movimentos)]
        )

        total_pago = sum(
            float(mov.get("valor", 0) or 0)
            for mov, _ in self._movimentos
            if mov.get("tipo") == "PAGAMENTO"
        )

        nome_loja = api.configuracoes().get("nome_loja") or "Vertex ERP"
        hoje = datetime.now().strftime("%d/%m/%Y")

        texto = (
            f"Olá, {self.cliente.get('nome', '')}! Tudo bem?\n\n"
            f"Segue o resumo atualizado do seu cadastro na {nome_loja}:\n\n"
            f"EXTRATO FINANCEIRO\n\n"
            f"Total de compras: {formatar_moeda(agr['total_comprado'])}\n"
            f"Total já pago: {formatar_moeda(total_pago)}\n"
            f"Saldo atual em aberto: {formatar_moeda(saldo)}\n\n"
            f"Última atualização: {hoje}\n\n"
            f"Caso queira conferir alguma compra ou pagamento, é só nos "
            f"chamar. Será um prazer ajudar!\n\n"
            f"Equipe {nome_loja}"
        )

        self._enviar_texto_whatsapp(texto, "Extrato Completo")

    def enviar_cobranca_whatsapp(self):
        """Mensagem de cobrança -- só faz sentido quando existe saldo
        devedor de verdade."""

        saldo = saldo_cliente(self.cliente["id"])

        if saldo <= 0:
            QMessageBox.information(
                self, "Cobrança", "Este cliente não tem saldo devedor."
            )
            return

        nome_loja = api.configuracoes().get("nome_loja") or "Vertex ERP"

        texto = (
            f"Olá, {self.cliente.get('nome', '')}! Tudo bem?\n\n"
            f"Estamos passando para lembrar, de forma amigável, que "
            f"consta em nosso sistema um saldo em aberto referente às "
            f"suas compras na {nome_loja}.\n\n"
            f"Saldo pendente: {formatar_moeda(saldo)}\n\n"
            f"Se o pagamento já foi realizado, por favor, desconsidere "
            f"esta mensagem. Caso precise conferir o histórico das "
            f"compras, combinar uma data ou tirar alguma dúvida, "
            f"estamos à disposição.\n\n"
            f"Agradecemos a sua atenção e preferência!\n\n"
            f"Equipe {nome_loja}"
        )

        self._enviar_texto_whatsapp(texto, "Enviar Cobrança")

    def _construir_pagina_observacoes(self):
        """Antes era a 4ª aba ('Observações'); agora mora dentro do
        painel lateral recolhível, embaixo do Resumo -- por isso ganha
        uma altura limitada (rolagem própria) em vez de ocupar a tela
        inteira como fazia quando era uma aba dedicada."""

        pagina = QFrame()
        pagina.setStyleSheet("background:transparent;")

        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        linha_nova = QVBoxLayout()
        linha_nova.setSpacing(6)

        self.campo_nova_observacao = CampoTexto(
            "Escreva uma observação..."
        )

        self.bt_add_observacao = BotaoPrimario("Adicionar")
        self.bt_add_observacao.setFixedHeight(36)
        self.bt_add_observacao.setAutoDefault(False)
        self.bt_add_observacao.clicked.connect(self.adicionar_observacao)

        linha_nova.addWidget(self.campo_nova_observacao)
        linha_nova.addWidget(self.bt_add_observacao)

        layout.addLayout(linha_nova)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # sem altura minima -- essa lista tem rolagem própria, não pode
        # ser o que impede o painel (e o diálogo inteiro) de encolher
        # numa tela menor (ver _dimensionar_e_centralizar)
        scroll.setMinimumHeight(0)
        scroll.setMaximumHeight(260)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        conteudo = QFrame()
        conteudo.setStyleSheet("background:transparent;")

        self.layout_observacoes = QVBoxLayout(conteudo)
        self.layout_observacoes.setContentsMargins(0, 0, 6, 0)
        self.layout_observacoes.setSpacing(8)
        self.layout_observacoes.addStretch()

        scroll.setWidget(conteudo)
        layout.addWidget(scroll)

        return pagina

    def _preencher_observacoes(self, observacoes):

        while self.layout_observacoes.count():
            item = self.layout_observacoes.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not observacoes:
            vazio = QLabel("Nenhuma observação registrada ainda.")
            vazio.setAlignment(Qt.AlignCenter)
            vazio.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_BASE}px; padding:20px;
            """)
            self.layout_observacoes.addWidget(vazio)
            self.layout_observacoes.addStretch()
            return

        for obs in observacoes:
            self.layout_observacoes.addWidget(self._linha_observacao(obs))

        self.layout_observacoes.addStretch()

    def _linha_observacao(self, obs):

        linha = Card()

        layout = QVBoxLayout(linha)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        cabecalho = QHBoxLayout()

        data = _parse_data(obs.get("criado_em"))
        texto_data = data.strftime("%d/%m/%Y %H:%M") if data else "—"

        lbl_data = QLabel(texto_data)
        lbl_data.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        bt_excluir = QPushButton("Excluir")
        bt_excluir.setCursor(Qt.PointingHandCursor)
        bt_excluir.setAutoDefault(False)
        bt_excluir.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; color:{tokens.ERRO};
                font-size:{tokens.TAMANHO_XS}px; font-weight:700;
            }}
            QPushButton:hover {{ text-decoration: underline; }}
        """)
        bt_excluir.clicked.connect(
            lambda _, oid=obs["id"]: self.excluir_observacao(oid)
        )

        cabecalho.addWidget(lbl_data)
        cabecalho.addStretch()
        cabecalho.addWidget(bt_excluir)

        lbl_texto = QLabel(obs.get("texto", ""))
        lbl_texto.setWordWrap(True)
        lbl_texto.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px;
        """)

        layout.addLayout(cabecalho)
        layout.addWidget(lbl_texto)

        return linha

    def _carregar_observacoes(self):
        rodar_em_thread(
            self,
            listar_observacoes_cliente,
            self.cliente["id"],
            ao_sucesso=self._preencher_observacoes,
        )

    def adicionar_observacao(self):

        texto = self.campo_nova_observacao.text().strip()

        if not texto:
            return

        self.bt_add_observacao.setEnabled(False)

        rodar_em_thread(
            self,
            criar_observacao_cliente,
            self.cliente["id"],
            texto,
            ao_sucesso=self._ao_adicionar_observacao_sucesso,
            ao_erro=self._ao_observacao_erro,
            ao_finalizar=self._ao_adicionar_observacao_finalizado,
        )

    def _ao_adicionar_observacao_sucesso(self, response):
        if response.status_code in (200, 201):
            self.campo_nova_observacao.clear()
            self._carregar_observacoes()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_adicionar_observacao_finalizado(self):
        self.bt_add_observacao.setEnabled(True)

    def _ao_observacao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def excluir_observacao(self, observacao_id):

        resposta = QMessageBox.question(
            self, "Excluir Observação", "Deseja excluir esta observação?"
        )

        if resposta != QMessageBox.Yes:
            return

        rodar_em_thread(
            self,
            excluir_observacao_cliente,
            self.cliente["id"],
            observacao_id,
            ao_sucesso=self._ao_excluir_observacao_sucesso,
            ao_erro=self._ao_observacao_erro,
        )

    def _ao_excluir_observacao_sucesso(self, response):
        if response.status_code == 200:
            self._carregar_observacoes()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _acoes_movimento(self, mov):
        """Botões de editar/excluir um lançamento errado -- direto na
        tabela, pra corrigir sem precisar apagar e recriar o cliente
        inteiro."""

        container = QFrame()
        container.setStyleSheet("background:transparent;")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        bt_editar = QPushButton()
        bt_editar.setIcon(icone("edit-2", cor=tokens.TEXTO_SECUNDARIO, tamanho=14))
        bt_editar.setFixedSize(26, 26)
        bt_editar.setCursor(Qt.PointingHandCursor)
        bt_editar.setToolTip("Corrigir lançamento")
        bt_editar.setAccessibleName("Corrigir lançamento")
        bt_editar.setStyleSheet(
            "QPushButton { background:transparent; border:none; }"
            f"QPushButton:hover {{ background:{tokens.FUNDO}; border-radius:6px; }}"
        )
        bt_editar.clicked.connect(
            lambda _, m=mov: self._editar_movimento_fiado(m)
        )

        bt_excluir = QPushButton()
        bt_excluir.setIcon(icone("trash-2", cor=tokens.ERRO, tamanho=14))
        bt_excluir.setFixedSize(26, 26)
        bt_excluir.setCursor(Qt.PointingHandCursor)
        bt_excluir.setToolTip("Excluir lançamento")
        bt_excluir.setAccessibleName("Excluir lançamento")
        bt_excluir.setStyleSheet(
            "QPushButton { background:transparent; border:none; }"
            f"QPushButton:hover {{ background:{tokens.ERRO_CLARO}; border-radius:6px; }}"
        )
        bt_excluir.clicked.connect(
            lambda _, m=mov: self._excluir_movimento_fiado(m)
        )

        layout.addWidget(bt_editar)
        layout.addWidget(bt_excluir)

        return container

    def _editar_movimento_fiado(self, mov):

        valor_atual = float(mov.get("valor", 0) or 0)

        novo_valor, ok = QInputDialog.getDouble(
            self,
            "Corrigir Lançamento",
            "Valor correto:",
            valor_atual,
            0.0,
            999999.0,
            2,
        )

        if not ok:
            return

        rodar_em_thread(
            self,
            editar_movimento,
            mov["id"],
            valor=novo_valor,
            ao_sucesso=self._ao_editar_movimento_sucesso,
            ao_erro=self._ao_movimento_mutacao_erro,
        )

    def _ao_editar_movimento_sucesso(self, response):

        if response.status_code != 200:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        dados = response.json()

        if dados.get("caixa_ajustado") is False:
            QMessageBox.warning(
                self,
                "Caixa não ajustado",
                "O lançamento foi corrigido, mas não havia caixa aberto "
                "pra ajustar automaticamente a diferença — confira o "
                "caixa manualmente se precisar.",
            )

        self.carregar()

    def _ao_movimento_mutacao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _excluir_movimento_fiado(self, mov):

        resposta = QMessageBox.question(
            self,
            "Excluir Lançamento",
            "Excluir este lançamento do fiado? Essa ação não pode ser desfeita.",
        )

        if resposta != QMessageBox.Yes:
            return

        rodar_em_thread(
            self,
            excluir_movimento,
            mov["id"],
            ao_sucesso=self._ao_excluir_movimento_sucesso,
            ao_erro=self._ao_movimento_mutacao_erro,
        )

    def _ao_excluir_movimento_sucesso(self, response):

        if response.status_code != 200:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        dados = response.json()

        if dados.get("caixa_ajustado") is False:
            QMessageBox.warning(
                self,
                "Caixa não ajustado",
                "O lançamento foi excluído, mas não havia caixa aberto "
                "pra estornar automaticamente o valor — confira o "
                "caixa manualmente se precisar.",
            )

        self.carregar()

    def _construir_filtros_timeline(self):
        """Filtros rápidos da timeline única (substituem as antigas
        abas Histórico/Compras/Pagamentos): chips de tipo + busca por
        texto, combinados na hora de exibir (ver _movimentos_filtrados).
        FlowLayout em vez de QHBoxLayout -- os 6 chips + a busca numa
        linha fixa forçavam o diálogo inteiro a não encolher abaixo
        dessa largura; aqui eles quebram pra linha de baixo sozinhos
        se não couberem."""

        layout = FlowLayout(espaco_h=8, espaco_v=8)

        self.botoes_filtro_timeline = {}

        opcoes = [
            ("TODOS", "Todos", "filter"),
            ("COMPRA", "Compras", "shopping-cart"),
            ("PAGAMENTO", "Pagamentos", "dollar-sign"),
            ("HAVER", "Haver", "gift"),
            ("AJUSTES", "Ajustes", "refresh-cw"),
            ("30DIAS", "Últimos 30 dias", "calendar"),
        ]

        for chave, texto, icone_nome in opcoes:

            botao = QPushButton(texto)
            botao.setCheckable(True)
            botao.setChecked(chave == "TODOS")
            botao.setCursor(Qt.PointingHandCursor)
            botao.setIcon(icone(
                icone_nome,
                cor=tokens.TEXTO_CLARO if chave == "TODOS" else tokens.TEXTO_SECUNDARIO,
                tamanho=13,
            ))
            botao.setStyleSheet(f"""
                QPushButton {{
                    background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                    border-radius:{tokens.RADIUS_PILL}px;
                    color:{tokens.TEXTO_SECUNDARIO}; font-size:{tokens.TAMANHO_XS}px;
                    font-weight:700; padding:6px 14px;
                }}
                QPushButton:checked {{
                    background:{tokens.PRIMARIA}; border-color:{tokens.PRIMARIA};
                    color:{tokens.TEXTO_CLARO};
                }}
                QPushButton:hover {{ border-color:{tokens.PRIMARIA}; }}
            """)
            botao.clicked.connect(
                lambda _, chave=chave, icone_nome=icone_nome: self._selecionar_filtro_timeline(chave, icone_nome)
            )

            self.botoes_filtro_timeline[chave] = botao
            layout.addWidget(botao)

        self.campo_busca_timeline = CampoTexto("Pesquisar na timeline...")
        self.campo_busca_timeline.setFixedWidth(220)
        self.campo_busca_timeline.setMinimumHeight(0)
        self.campo_busca_timeline.setFixedHeight(32)
        self.campo_busca_timeline.textChanged.connect(self._on_busca_timeline)

        layout.addWidget(self.campo_busca_timeline)

        return layout

    _ICONES_FILTRO_TIMELINE = {
        "TODOS": "filter", "COMPRA": "shopping-cart", "PAGAMENTO": "dollar-sign",
        "HAVER": "gift", "AJUSTES": "refresh-cw", "30DIAS": "calendar",
    }

    def _selecionar_filtro_timeline(self, chave, _icone_nome=None):

        self._filtro_timeline = chave

        for k, botao in self.botoes_filtro_timeline.items():
            selecionado = k == chave
            botao.setChecked(selecionado)
            botao.setIcon(icone(
                self._ICONES_FILTRO_TIMELINE.get(k, "filter"),
                cor=tokens.TEXTO_CLARO if selecionado else tokens.TEXTO_SECUNDARIO,
                tamanho=13,
            ))

        self._timeline_qtd_exibida = self._TIMELINE_PAGINA
        self._preencher_timeline()

    def _on_busca_timeline(self, texto):

        self._busca_timeline = texto.strip().lower()
        self._timeline_qtd_exibida = self._TIMELINE_PAGINA
        self._preencher_timeline()

    def _passa_filtro_timeline(self, mov):

        tipo = mov.get("tipo", "")
        estorno = self._e_estorno(mov)
        filtro = self._filtro_timeline

        if filtro == "TODOS":
            return True
        if filtro == "COMPRA":
            return tipo == "COMPRA" and not estorno
        if filtro == "PAGAMENTO":
            return tipo == "PAGAMENTO" and not estorno
        if filtro == "HAVER":
            return tipo == "HAVER" and not estorno
        if filtro == "AJUSTES":
            return estorno
        if filtro == "30DIAS":
            data = _parse_data(mov.get("data"))
            return bool(data) and (datetime.now() - data).days <= 30

        return True

    def _movimentos_filtrados(self):

        resultado = []

        for mov, saldo_apos in self._movimentos:

            if not self._passa_filtro_timeline(mov):
                continue

            if self._busca_timeline:
                alvo = (
                    f"{self._descricao_com_itens(mov)} "
                    f"{mov.get('descricao', '')}"
                ).lower()
                if self._busca_timeline not in alvo:
                    continue

            resultado.append((mov, saldo_apos))

        return resultado

    def _construir_timeline(self):
        """Linha do tempo única (Compra/Pagamento/Haver/Ajuste), no
        lugar das antigas abas Histórico/Compras/Pagamentos -- ocupa
        praticamente toda a área principal (~70% da tela) e tem rolagem
        própria e incremental (ver _verificar_scroll_timeline)."""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        scroll.verticalScrollBar().valueChanged.connect(
            self._verificar_scroll_timeline
        )

        conteudo = QFrame()
        conteudo.setStyleSheet("background:transparent;")

        self.layout_timeline = QVBoxLayout(conteudo)
        self.layout_timeline.setContentsMargins(0, 0, 6, 0)
        self.layout_timeline.setSpacing(8)
        self.layout_timeline.addStretch()

        scroll.setWidget(conteudo)
        self.scroll_timeline = scroll

        return scroll

    def _verificar_scroll_timeline(self, valor):
        """Scroll incremental: só monta os próximos 30 lançamentos
        quando o usuário chega perto do fim da lista já renderizada --
        evita montar centenas de widgets de uma vez só quando o cliente
        tem um histórico grande."""

        barra = self.scroll_timeline.verticalScrollBar()

        if barra.maximum() > 0 and valor >= barra.maximum() - 60:
            self._carregar_mais_timeline()

    def _carregar_mais_timeline(self):

        total_filtrado = len(self._movimentos_filtrados())

        if self._timeline_qtd_exibida >= total_filtrado:
            return

        self._timeline_qtd_exibida += self._TIMELINE_PAGINA
        self._preencher_timeline()

    def _preencher_timeline(self):

        while self.layout_timeline.count():
            item = self.layout_timeline.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        historico = self._movimentos_filtrados()

        if not historico:
            vazio = QLabel("Nenhuma movimentação encontrada.")
            vazio.setAlignment(Qt.AlignCenter)
            vazio.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_BASE}px; padding:20px;
            """)
            self.layout_timeline.addWidget(vazio)
            self.layout_timeline.addStretch()
            return

        visiveis = historico[: self._timeline_qtd_exibida]

        for mov, saldo_apos in visiveis:
            self.layout_timeline.addWidget(self._linha_timeline(mov, saldo_apos))

        texto_contagem = (
            f"Mostrando {len(visiveis)} de {len(historico)} registros — "
            "role pra ver mais"
            if len(historico) > len(visiveis)
            else (
                "Mostrando 1 registro" if len(visiveis) == 1
                else f"Mostrando {len(visiveis)} registros"
            )
        )
        lbl_mais = QLabel(texto_contagem)
        lbl_mais.setAlignment(Qt.AlignCenter)
        lbl_mais.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; padding:10px;
        """)
        self.layout_timeline.addWidget(lbl_mais)

        self.layout_timeline.addStretch()

    def _linha_timeline(self, mov, saldo_apos):

        tipo = mov.get("tipo", "")
        estorno = self._e_estorno(mov)

        if estorno:
            cor = tokens.ERRO
            icone_nome = "refresh-cw"
            rotulo_tipo = "Ajuste"
        elif tipo == "HAVER":
            cor = tokens.ALERTA
            icone_nome = "gift"
            rotulo_tipo = "Haver"
        elif tipo == "COMPRA":
            cor = tokens.PRIMARIA
            icone_nome = "shopping-cart"
            rotulo_tipo = "Compra"
        else:
            cor = tokens.SECUNDARIA
            icone_nome = "check"
            rotulo_tipo = "Pagamento"

        linha = QFrame()
        linha.setStyleSheet(f"""
            background: {tokens.CARD};
            border: 1px solid {tokens.BORDA};
            border-left: 3px solid {cor};
            border-radius: {tokens.RADIUS_SM}px;
        """)

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        lbl_icone = QLabel()
        lbl_icone.setPixmap(icone_pixmap(icone_nome, cor=cor, tamanho=18))
        lbl_icone.setStyleSheet("background:transparent; border:none;")
        layout.addWidget(lbl_icone, 0, Qt.AlignTop)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(2)

        data = str(mov.get("data", ""))
        if "T" in data:
            data = data.replace("T", " ")[:16]

        linha_topo = QHBoxLayout()
        linha_topo.setSpacing(8)

        lbl_tipo = QLabel(rotulo_tipo)
        cor_pilula = QColor(cor)
        lbl_tipo.setStyleSheet(f"""
            background: rgba({cor_pilula.red()}, {cor_pilula.green()}, {cor_pilula.blue()}, 0.14);
            border:none; border-radius:{tokens.RADIUS_PILL}px; color:{cor};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800; padding: 2px 8px;
        """)

        lbl_data = QLabel(data)
        lbl_data.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        linha_topo.addWidget(lbl_tipo)
        linha_topo.addWidget(lbl_data)
        linha_topo.addStretch()

        lbl_descricao = QLabel(self._descricao_com_itens(mov))
        lbl_descricao.setWordWrap(True)
        lbl_descricao.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:600;
        """)

        col_texto.addLayout(linha_topo)
        col_texto.addWidget(lbl_descricao)

        layout.addLayout(col_texto, stretch=1)

        forma = mov.get("forma_pagamento")

        if forma:
            texto_forma = NOMES_FORMA_FIADO.get(forma, forma)
            layout.addWidget(Badge(texto_forma, "neutro"), 0, Qt.AlignTop)

        col_valor = QVBoxLayout()
        col_valor.setSpacing(2)

        valor = float(mov.get("valor", 0) or 0)
        texto_valor = (
            f"+ {formatar_moeda(valor)}"
            if tipo == "COMPRA"
            else f"- {formatar_moeda(valor)}"
        )

        lbl_valor = QLabel(texto_valor)
        lbl_valor.setAlignment(Qt.AlignRight)
        lbl_valor.setStyleSheet(f"""
            background:transparent; border:none; color:{cor};
            font-size:{tokens.TAMANHO_MD}px; font-weight:800;
        """)

        lbl_saldo = QLabel(f"Saldo: {formatar_moeda(saldo_apos)}")
        lbl_saldo.setAlignment(Qt.AlignRight)
        lbl_saldo.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_valor.addWidget(lbl_valor)
        col_valor.addWidget(lbl_saldo)

        layout.addLayout(col_valor)

        layout.addWidget(self._acoes_movimento(mov), 0, Qt.AlignTop)

        return linha

    _LARGURA_PAINEL_LATERAL = 280

    def _construir_painel_lateral(self):
        """Painel lateral agora é recolhível (botão no topo) -- quando
        recolhido, libera espaço horizontal pra timeline, que é a área
        que mais importa no dia a dia. As Observações, que antes eram
        uma aba própria, moram aqui embaixo do Resumo."""

        self.painel_lateral_expandido = True

        wrapper = QFrame()
        wrapper.setStyleSheet("background:transparent;")
        wrapper.setFixedWidth(self._LARGURA_PAINEL_LATERAL)

        layout_wrapper = QVBoxLayout(wrapper)
        layout_wrapper.setContentsMargins(0, 0, 0, 0)
        layout_wrapper.setSpacing(6)

        linha_toggle = QHBoxLayout()
        linha_toggle.addStretch()

        self.bt_recolher_painel = QPushButton("Recolher ›")
        self.bt_recolher_painel.setCursor(Qt.PointingHandCursor)
        self.bt_recolher_painel.setFixedHeight(26)
        self.bt_recolher_painel.setToolTip("Recolher o painel de resumo")
        self.bt_recolher_painel.clicked.connect(self._alternar_painel_lateral)
        self.bt_recolher_painel.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px; color:{tokens.TEXTO_SECUNDARIO};
                font-size:{tokens.TAMANHO_XS}px; font-weight:700; padding:0 10px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)

        linha_toggle.addWidget(self.bt_recolher_painel)
        layout_wrapper.addLayout(linha_toggle)

        self.painel_lateral = SecaoCard("Resumo", "bar-chart-2")

        self.lbl_resumo_total_comprado = self._linha_resumo(
            self.painel_lateral, "Total Comprado"
        )
        self.lbl_resumo_total_pago = self._linha_resumo(
            self.painel_lateral, "Total Pago"
        )
        self.lbl_resumo_saldo_atual = self._linha_resumo(
            self.painel_lateral, "Saldo Atual"
        )
        self.lbl_resumo_maior_compra = self._linha_resumo(
            self.painel_lateral, "Maior Compra"
        )
        self.lbl_resumo_ultima_compra = self._linha_resumo(
            self.painel_lateral, "Última Compra"
        )
        self.lbl_resumo_ticket_medio = self._linha_resumo(
            self.painel_lateral, "Ticket Médio"
        )
        self.lbl_resumo_total_compras = self._linha_resumo(
            self.painel_lateral, "Total de Compras"
        )

        separador = QFrame()
        separador.setFixedHeight(1)
        separador.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        self.painel_lateral.corpo.addSpacing(4)
        self.painel_lateral.corpo.addWidget(separador)

        lbl_obs_titulo = QLabel("Observações")
        lbl_obs_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)
        self.painel_lateral.corpo.addWidget(lbl_obs_titulo)
        self.painel_lateral.corpo.addWidget(self._construir_pagina_observacoes())

        separador_2 = QFrame()
        separador_2.setFixedHeight(1)
        separador_2.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        self.painel_lateral.corpo.addSpacing(4)
        self.painel_lateral.corpo.addWidget(separador_2)

        bt_excluir = BotaoPerigo("Excluir Cliente", icone_nome="trash-2")
        bt_excluir.setMinimumHeight(38)
        bt_excluir.setAutoDefault(False)
        bt_excluir.clicked.connect(self.excluir_cliente_atual)
        self.painel_lateral.corpo.addWidget(bt_excluir)

        bt_lgpd_exportar = BotaoSecundario("Exportar (LGPD)", icone_nome="download")
        bt_lgpd_exportar.setMinimumHeight(38)
        bt_lgpd_exportar.setAutoDefault(False)
        bt_lgpd_exportar.clicked.connect(self.exportar_dados_lgpd_atual)
        self.painel_lateral.corpo.addWidget(bt_lgpd_exportar)

        bt_lgpd_remover = BotaoPerigo("Remover (LGPD)", icone_nome="lock")
        bt_lgpd_remover.setMinimumHeight(38)
        bt_lgpd_remover.setAutoDefault(False)
        bt_lgpd_remover.clicked.connect(self.remover_dados_lgpd_atual)
        self.painel_lateral.corpo.addWidget(bt_lgpd_remover)

        # o painel inteiro (Resumo + Observações) fica dentro da sua
        # própria rolagem vertical -- em telas mais baixas (ex.:
        # 1366x768) o conteúdo dele sozinho já passaria dos 90% de
        # altura da tela; sem isso, ele forçaria o diálogo inteiro a
        # crescer além da área útil do Windows pra caber tudo sem
        # cortar nada. Só rolagem vertical: a largura já é fixa.
        self.scroll_painel_lateral = QScrollArea()
        self.scroll_painel_lateral.setWidgetResizable(True)
        self.scroll_painel_lateral.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_painel_lateral.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }"
        )
        self.scroll_painel_lateral.setWidget(self.painel_lateral)

        layout_wrapper.addWidget(self.scroll_painel_lateral, stretch=1)

        self._painel_lateral_wrapper = wrapper

        return wrapper

    def _alternar_painel_lateral(self):

        self.painel_lateral_expandido = not self.painel_lateral_expandido

        self.scroll_painel_lateral.setVisible(self.painel_lateral_expandido)

        if self.painel_lateral_expandido:
            self._painel_lateral_wrapper.setFixedWidth(
                self._LARGURA_PAINEL_LATERAL
            )
            self.bt_recolher_painel.setText("Recolher ›")
        else:
            self._painel_lateral_wrapper.setFixedWidth(112)
            self.bt_recolher_painel.setText("‹ Resumo")

    def _linha_resumo(self, secao, titulo):

        linha = QVBoxLayout()
        linha.setSpacing(0)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        lbl_valor = QLabel("—")
        lbl_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:700;
        """)

        linha.addWidget(lbl_titulo)
        linha.addWidget(lbl_valor)

        secao.corpo.addLayout(linha)

        return lbl_valor

    def _construir_rodape(self):
        """Editar Cliente subiu pro cabeçalho (junto do resto das ações
        de contato) e Excluir/LGPD desceram pro painel lateral (embaixo
        de Observações) -- esse rodapé agora só segura o "Fechar",
        sempre no mesmo lugar previsível pra fechar a ficha."""

        rodape = QFrame()
        rodape.setStyleSheet(f"""
            background:{tokens.CARD}; border-top:1px solid {tokens.BORDA};
        """)

        layout = QHBoxLayout(rodape)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(10)

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.setMinimumHeight(42)
        bt_fechar.setAutoDefault(False)
        bt_fechar.clicked.connect(self.accept)

        layout.addStretch()
        layout.addWidget(bt_fechar)

        return rodape

    # ======================================
    # DADOS
    # ======================================

    def _atualizar_cabecalho(self, cliente):

        self.lbl_titulo.setText(cliente["nome"])

        ativo = cliente.get("ativo", True)
        self.badge_ativo.setText("Ativo" if ativo else "Inativo")
        variante = "sucesso" if ativo else "erro"
        fundo, cor_texto = Badge.variantes()[variante]
        self.badge_ativo.setStyleSheet(f"""
            background: {fundo}; color: {cor_texto};
            border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
            font-weight: 600; padding: 3px 10px;
        """)

        self.lbl_subtitulo.setText(cliente.get("telefone") or "Sem telefone")

        self.bt_whatsapp.setEnabled(bool(cliente.get("telefone")))
        self.bt_ligar.setEnabled(bool(cliente.get("telefone")))
        self.bt_email.setEnabled(bool(cliente.get("email")))

    def _atualizar_avatar(self, cliente):

        if not cliente.get("tem_foto"):
            return

        rodar_em_thread(
            self,
            obter_foto_cliente,
            cliente["id"],
            ao_sucesso=self._ao_atualizar_avatar_sucesso,
        )

    def _ao_atualizar_avatar_sucesso(self, foto_bytes):

        if not foto_bytes:
            return

        pixmap = QPixmap()
        pixmap.loadFromData(foto_bytes)

        self.avatar.setStyleSheet("background:transparent;")
        self.avatar.setPixmap(_pixmap_circular(pixmap, self.avatar.width()))

    def editar_cliente(self):

        from telas.cadastro_cliente import CadastroClienteDialog

        dialogo = CadastroClienteDialog(self.cliente, parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        if dialogo.cliente_salvo:
            self.cliente = dialogo.cliente_salvo
            self._atualizar_cabecalho(self.cliente)
            self._atualizar_avatar(self.cliente)

    def excluir_cliente_atual(self):

        from services.cliente_service import excluir_cliente

        resposta = QMessageBox.question(
            self,
            "Excluir Cliente",
            f"Deseja desativar o cliente\n\n{self.cliente['nome']} ?"
        )

        if resposta != QMessageBox.Yes:
            return

        rodar_em_thread(
            self,
            excluir_cliente,
            self.cliente["id"],
            ao_sucesso=self._ao_excluir_cliente_sucesso,
            ao_erro=self._ao_movimento_mutacao_erro,
        )

    def _ao_excluir_cliente_sucesso(self, response):

        if response.status_code == 200:

            dados = response.json()

            if dados.get("aprovacao_pendente"):
                QMessageBox.information(
                    self,
                    "Aguardando aprovação",
                    dados.get("mensagem")
                    or "Pedido enviado — aguardando aprovação de um "
                    "administrador.",
                )
                # nao fecha a ficha: o cliente continua existindo ate
                # alguem aprovar
                return

            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def exportar_dados_lgpd_atual(self):

        from services.cliente_service import exportar_dados_lgpd

        response = exportar_dados_lgpd(self.cliente["id"])

        if response.status_code != 200:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        nome_arquivo = f"dados_lgpd_{self.cliente['nome'].replace(' ', '_')}.json"

        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Dados do Cliente (LGPD)",
            nome_arquivo,
            "Arquivo JSON (*.json)",
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".json"):
            caminho += ".json"

        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(response.json(), arquivo, ensure_ascii=False, indent=2)

        QMessageBox.information(
            self,
            "Sucesso",
            "Dados do cliente exportados com sucesso.",
        )

    def remover_dados_lgpd_atual(self):

        from services.cliente_service import remover_dados_lgpd

        resposta = QMessageBox.question(
            self,
            "Remover dados pessoais (LGPD)",
            "Isso vai apagar PERMANENTEMENTE os dados pessoais de "
            f"{self.cliente['nome']} (nome, CPF/CNPJ, telefone, "
            "e-mail, endereço, foto e observações) -- essa ação não "
            "pode ser desfeita.\n\n"
            "O histórico de vendas e fiado continua guardado (sem "
            "identificar mais a pessoa), pra manter os registros "
            "contábeis da loja.\n\n"
            "Tem certeza que quer continuar?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = remover_dados_lgpd(self.cliente["id"])

        if response.status_code == 200:
            QMessageBox.information(
                self,
                "Sucesso",
                response.json().get("mensagem") or "Dados removidos com sucesso.",
            )
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def _descricao_com_itens(self, mov):
        """Pra compras vindas de uma venda de verdade do PDV, troca o
        texto generico ("Venda #12") pela lista dos produtos —
        exatamente o que aparecia escrito a mao na ficha de papel.
        Lancamentos manuais (sem venda_id) ja tem os itens digitados
        direto na descricao, entao ficam como estao."""

        venda_id = mov.get("venda_id")
        descricao = mov.get("descricao") or ""

        if mov.get("tipo") != "COMPRA" or venda_id is None:
            return descricao

        venda = self._vendas_por_id.get(venda_id)

        if not venda or not venda.get("itens"):
            return descricao

        partes = []

        for item in venda["itens"]:
            nome = self._nomes_produto.get(
                item.get("produto_id"), "Produto removido"
            )
            quantidade = item.get("quantidade", 1)
            partes.append(f"{nome} x{quantidade}")

        return ", ".join(partes) if partes else descricao

    @staticmethod
    def _e_estorno(mov):
        return (mov.get("descricao") or "").startswith("Estorno")

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            _buscar_dados_ficha_cliente,
            self.cliente["id"],
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_lancar_fiado.setEnabled(not carregando)
        self.bt_haver.setEnabled(not carregando)
        # bt_pagar fica de fora -- carregar() decide se ele deveria
        # estar habilitado (saldo > 0) assim que o saldo chegar

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar a ficha do cliente.\n{erro}"
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self.bt_lancar_fiado.setEnabled(True)
        self.bt_haver.setEnabled(True)

    def _ao_carregar_sucesso(self, resultado):

        saldo, self._vendas_por_id, self._nomes_produto, movimentos = resultado

        self.lbl_saldo_valor.setText(formatar_moeda(saldo))
        self.lbl_saldo_valor.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_SM}px;
            font-weight:800;
            color:{tokens.ERRO if saldo > 0 else tokens.SECUNDARIA};
        """)

        self.bt_pagar.setEnabled(saldo > 0)

        # ordem cronologica (mais antigo primeiro) pra calcular o saldo
        # corrido — depois inverte só na hora de exibir
        movimentos_cron = sorted(
            movimentos, key=lambda m: m.get("data", "")
        )

        saldo_corrido = 0.0
        historico_calculado = []

        for mov in movimentos_cron:

            valor = float(mov.get("valor", 0) or 0)

            if mov.get("tipo") == "COMPRA":
                saldo_corrido += valor
            else:
                saldo_corrido -= valor

            historico_calculado.append((mov, saldo_corrido))

        historico_calculado.reverse()

        self._movimentos = historico_calculado
        self._timeline_qtd_exibida = self._TIMELINE_PAGINA

        self._preencher_timeline()

        self._atualizar_stats(movimentos_cron, saldo)
        self._carregar_observacoes()

    def _atualizar_stats(self, movimentos_cron, saldo_atual):

        agr = cliente_analise.calcular_agregados(self.cliente, movimentos_cron)

        total_comprado = agr["total_comprado"]
        total_pago = sum(
            float(m.get("valor", 0) or 0)
            for m in movimentos_cron
            if m.get("tipo") == "PAGAMENTO"
        )
        qtd_compras = agr["qtd_compras"]
        maior_compra = agr["maior_compra"]
        ticket_medio = total_comprado / qtd_compras if qtd_compras else 0

        def _data_curta(data):
            return data.strftime("%d/%m/%Y") if data else "—"

        def _dias_texto(dias):
            if dias is None:
                return "—"
            return "Hoje" if dias == 0 else f"{dias} dia(s)"

        # linha de mini-cards
        self.lbl_total_comprado.setText(formatar_moeda(total_comprado))
        self.lbl_total_pago_card.setText(formatar_moeda(total_pago))
        self.lbl_ultima_compra.setText(_data_curta(agr["ultima_compra"]))
        self.lbl_ultimo_pagamento.setText(_data_curta(agr["ultimo_pagamento"]))
        self.lbl_dias_desde_ultima_compra.setText(
            _dias_texto(agr["dias_desde_ultima_compra"])
        )
        self.lbl_cliente_desde.setText(_data_curta(agr["criado_em"]))

        self.lbl_status_financeiro.setText(
            cliente_analise.status_financeiro(agr)
        )

        pontuacao = cliente_analise.calcular_pontuacao(agr)
        emoji_pont, _, texto_pontuacao = pontuacao.partition(" ")
        self.lbl_score.setText(texto_pontuacao or pontuacao)

        variante_pontuacao = {
            "🔴": "erro", "🟠": "alerta", "🟡": "alerta",
            "🔵": "info", "🟢": "sucesso",
        }.get(emoji_pont, "neutro")
        fundo_pont, cor_texto_pont = Badge.variantes()[variante_pontuacao]
        self.badge_pontuacao.setText(texto_pontuacao or pontuacao)
        self.badge_pontuacao.setStyleSheet(f"""
            background: {fundo_pont}; color: {cor_texto_pont};
            border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
            font-weight: 600; padding: 3px 10px;
        """)
        self.badge_pontuacao.setVisible(True)

        limite_credito = self.cliente.get("limite_credito")
        self.lbl_limite_credito.setText(
            formatar_moeda(limite_credito) if limite_credito else "Sem limite"
        )

        aviso = cliente_analise.calcular_aviso(agr)
        emoji_aviso, _, texto_aviso = aviso.partition(" ")
        cor_fundo, cor_texto = {
            "🔴": (tokens.ERRO_CLARO, tokens.ERRO),
            "🟡": (tokens.ALERTA_CLARO, tokens.ALERTA),
            "🟢": (tokens.SUCESSO_CLARO, tokens.SECUNDARIA_HOVER),
        }.get(emoji_aviso, (tokens.FUNDO, tokens.TEXTO_SECUNDARIO))

        self.lbl_aviso_status.setText(texto_aviso or aviso)
        self.lbl_aviso_status.setStyleSheet(f"""
            background:{cor_fundo}; color:{cor_texto}; border:none;
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            border-radius:{tokens.RADIUS_SM}px; padding:6px 10px;
        """)

        # painel lateral
        self.lbl_resumo_total_comprado.setText(formatar_moeda(total_comprado))
        self.lbl_resumo_total_pago.setText(formatar_moeda(total_pago))
        self.lbl_resumo_saldo_atual.setText(formatar_moeda(saldo_atual))
        self.lbl_resumo_maior_compra.setText(formatar_moeda(maior_compra))
        self.lbl_resumo_ultima_compra.setText(_data_curta(agr["ultima_compra"]))
        self.lbl_resumo_ticket_medio.setText(formatar_moeda(ticket_medio))
        self.lbl_resumo_total_compras.setText(str(qtd_compras))

    def registrar_pagamento(self):

        self.bt_pagar.setEnabled(False)
        rodar_em_thread(
            self,
            saldo_cliente,
            self.cliente["id"],
            ao_sucesso=self._ao_saldo_para_pagamento_sucesso,
            ao_erro=self._ao_movimento_mutacao_erro,
            ao_finalizar=self._ao_saldo_pre_check_finalizado,
        )

    def _ao_saldo_pre_check_finalizado(self):
        self.bt_pagar.setEnabled(True)

    def _ao_saldo_para_pagamento_sucesso(self, saldo):

        if saldo <= 0:
            QMessageBox.information(
                self,
                "Fiado",
                "Este cliente não tem saldo devedor.",
            )
            return

        dialogo = RegistrarPagamentoDialog(
            self.cliente,
            saldo,
            parent=self,
        )

        if dialogo.exec() != QDialog.Accepted:
            return

        self.carregar()

    def lancar_fiado(self):

        self.bt_lancar_fiado.setEnabled(False)
        rodar_em_thread(
            self,
            saldo_cliente,
            self.cliente["id"],
            ao_sucesso=self._ao_saldo_para_fiado_sucesso,
            ao_erro=self._ao_movimento_mutacao_erro,
            ao_finalizar=self._ao_saldo_fiado_finalizado,
        )

    def _ao_saldo_fiado_finalizado(self):
        self.bt_lancar_fiado.setEnabled(True)

    def _ao_saldo_para_fiado_sucesso(self, saldo_atual):

        dialogo = LancarFiadoDialog(self.cliente, saldo_atual, parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        self.carregar()

    def lancar_haver(self):

        self.bt_haver.setEnabled(False)
        rodar_em_thread(
            self,
            saldo_cliente,
            self.cliente["id"],
            ao_sucesso=self._ao_saldo_para_haver_sucesso,
            ao_erro=self._ao_movimento_mutacao_erro,
            ao_finalizar=self._ao_saldo_haver_finalizado,
        )

    def _ao_saldo_haver_finalizado(self):
        self.bt_haver.setEnabled(True)

    def _ao_saldo_para_haver_sucesso(self, saldo):

        if saldo <= 0:
            QMessageBox.information(
                self,
                "Haver",
                "Este cliente não tem saldo devedor pra aplicar um crédito.",
            )
            return

        dialogo = LancarHaverDialog(self.cliente, saldo, parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        self.carregar()

    # ======================================
    # EXTRATO (PDF) / EXPORTAR CSV
    # ======================================

    def _montar_html_extrato(self):

        config = api.configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"
        telefone_loja = config.get("telefone") or ""

        usuario = api.me()
        responsavel = usuario.get("nome") or "—"

        saldo = saldo_cliente(self.cliente["id"])
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        linhas_tabela = []

        for mov, saldo_apos in reversed(self._movimentos):

            data = str(mov.get("data", ""))
            if "T" in data:
                data = data.replace("T", " ")[:16]

            tipo = mov.get("tipo")
            valor = float(mov.get("valor", 0) or 0)
            descricao = self._descricao_com_itens(mov)

            debito = (
                f"<span style='color:#DC2626;'>{formatar_moeda(valor)}</span>"
                if tipo == "COMPRA" else ""
            )
            credito = (
                f"<span style='color:#16A34A;'>{formatar_moeda(valor)}</span>"
                if tipo == "PAGAMENTO" else ""
            )

            # zebra striping feito aqui (não em CSS :nth-child, que o
            # QTextDocument do Qt não entende)
            cor_fundo = "#FFFFFF" if len(linhas_tabela) % 2 == 0 else "#F8FAFC"

            linhas_tabela.append(
                f"<tr style='background:{cor_fundo};'>"
                f"<td style='padding:6px 8px; border-bottom:1px solid #E5E7EB;'>{data}</td>"
                f"<td style='padding:6px 8px; border-bottom:1px solid #E5E7EB;'>{descricao}</td>"
                f"<td align='right' style='padding:6px 8px; border-bottom:1px solid #E5E7EB;'>{debito}</td>"
                f"<td align='right' style='padding:6px 8px; border-bottom:1px solid #E5E7EB;'>{credito}</td>"
                f"<td align='right' style='padding:6px 8px; border-bottom:1px solid #E5E7EB;'>{formatar_moeda(saldo_apos)}</td>"
                f"</tr>"
            )

        linhas_html = "".join(linhas_tabela) or (
            "<tr><td colspan='5' align='center' style='padding:10px;'>"
            "Nenhuma movimentação registrada.</td></tr>"
        )

        observacoes = listar_observacoes_cliente(self.cliente["id"])

        linhas_observacoes = "".join(
            f"<p style='margin:4px 0;'>"
            f"<b>{(_parse_data(obs.get('criado_em')) or datetime.now()).strftime('%d/%m/%Y')}:</b> "
            f"{obs.get('texto', '')}</p>"
            for obs in observacoes
        )

        bloco_observacoes = (
            f"<h3>Observações</h3>{linhas_observacoes}"
            if linhas_observacoes
            else ""
        )

        return f"""
        <body style="font-family: Arial; font-size: 10pt; color:#1E293B;">
        <table width="100%" style="margin-bottom:14px;">
            <tr><td style="background:#2563EB; height:4px; font-size:1px;">&nbsp;</td></tr>
        </table>
        <div style="text-align:center;">
            <h2 style="margin:2px 0;">{nome_loja}</h2>
            {f"<p style='margin:0; color:#64748B;'>WhatsApp: {telefone_loja}</p>" if telefone_loja else ""}
        </div>
        <table width="100%" style="margin:14px 0;">
            <tr><td style="background:#2563EB; padding:8px; text-align:center;">
                <span style="color:#FFFFFF; font-size:12pt; font-weight:bold;">
                    EXTRATO FINANCEIRO
                </span>
            </td></tr>
        </table>
        <table width="100%" cellspacing="4">
            <tr><td style="color:#64748B;"><b>Cliente:</b></td><td>{self.cliente.get('nome', '')}</td></tr>
            <tr><td style="color:#64748B;"><b>CPF/CNPJ:</b></td><td>{self.cliente.get('cpf_cnpj') or '—'}</td></tr>
            <tr><td style="color:#64748B;"><b>Telefone:</b></td><td>{self.cliente.get('telefone') or '—'}</td></tr>
            <tr><td style="color:#64748B;"><b>Emitido em:</b></td><td>{agora}</td></tr>
        </table>
        <h4 style="margin:16px 0 6px; color:#1E293B;">MOVIMENTAÇÕES</h4>
        <table style="width:100%; border-collapse:collapse; border:1px solid #E5E7EB;">
            <tr style="background:#EFF6FF;">
                <th style="padding:7px 8px; text-align:left; color:#1E3A8A;">Data</th>
                <th style="padding:7px 8px; text-align:left; color:#1E3A8A;">Descrição</th>
                <th style="padding:7px 8px; text-align:right; color:#1E3A8A;">Débito</th>
                <th style="padding:7px 8px; text-align:right; color:#1E3A8A;">Crédito</th>
                <th style="padding:7px 8px; text-align:right; color:#1E3A8A;">Saldo</th>
            </tr>
            {linhas_html}
        </table>
        {bloco_observacoes}
        <table width="100%" style="margin-top:14px;">
            <tr><td style="background:#EFF6FF; padding:10px 14px; text-align:right;">
                <span style="font-size:8pt; color:#2563EB; font-weight:bold;">
                    TOTAL DEVEDOR
                </span><br>
                <span style="font-size:15pt; color:#1E293B; font-weight:bold;">
                    {formatar_moeda(saldo)}
                </span>
            </td></tr>
        </table>
        <p style="margin:8px 0 0; color:#64748B; font-size:9pt;">
            Responsável pela emissão: {responsavel}
        </p>
        </body>
        """

    def _montar_documento_extrato(self):

        documento = QTextDocument()
        documento.setDefaultFont(QFont(tokens.FONTE_FAMILIA_PADRAO, 10))
        documento.setHtml(self._montar_html_extrato())

        return documento

    def _montar_movimentos_extrato_termico(self):
        """Mesma lista usada no HTML (ver _montar_html_extrato), só que
        como dicts simples -- formato que impressora_termica_service
        espera, sem acoplar esse serviço ao formato interno de `mov`."""

        movimentos = []

        for mov, saldo_apos in reversed(self._movimentos):

            data = str(mov.get("data", ""))
            if "T" in data:
                data = data.replace("T", " ")[:16]

            movimentos.append({
                "data": data,
                "descricao": self._descricao_com_itens(mov),
                "tipo": mov.get("tipo"),
                "valor": mov.get("valor", 0),
                "saldo_apos": saldo_apos,
            })

        return movimentos

    def imprimir_extrato(self):

        config_impressora = preferencias_service.carregar_impressora_termica()

        if config_impressora and config_impressora.get("ativa"):

            saldo = saldo_cliente(self.cliente["id"])
            usuario = api.me()
            responsavel = usuario.get("nome") or "—"
            observacoes = listar_observacoes_cliente(self.cliente["id"])

            ok, erro = impressora_termica_service.imprimir_extrato(
                self.cliente,
                self._montar_movimentos_extrato_termico(),
                observacoes,
                saldo,
                responsavel,
                api.configuracoes(),
                config_impressora,
            )

            if ok:
                return

            resposta = QMessageBox.question(
                self,
                "Falha na impressora térmica",
                f"{erro}\n\nQuer tentar imprimir pela janela normal do Windows?",
            )

            if resposta != QMessageBox.Yes:
                return

        printer = QPrinter(QPrinter.HighResolution)

        dialogo = QPrintDialog(printer, self)

        if dialogo.exec() != QPrintDialog.Accepted:
            return

        self._montar_documento_extrato().print_(printer)

    def exportar_csv(self):

        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Extrato (CSV)",
            f"extrato_{self.cliente['nome'].replace(' ', '_')}.csv",
            "Arquivo CSV (*.csv)",
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".csv"):
            caminho += ".csv"

        try:
            with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:

                escritor = csv.writer(arquivo, delimiter=";")
                escritor.writerow(
                    ["Data", "Tipo", "Descrição", "Forma Pagamento", "Valor", "Saldo Após"]
                )

                for mov, saldo_apos in reversed(self._movimentos):

                    data = str(mov.get("data", ""))
                    if "T" in data:
                        data = data.replace("T", " ")[:16]

                    forma = mov.get("forma_pagamento")
                    texto_forma = NOMES_FORMA_FIADO.get(forma, forma) if forma else ""

                    escritor.writerow([
                        data,
                        mov.get("tipo", ""),
                        self._descricao_com_itens(mov),
                        texto_forma,
                        f"{float(mov.get('valor', 0) or 0):.2f}",
                        f"{saldo_apos:.2f}",
                    ])

            QMessageBox.information(
                self, "Sucesso", "Extrato exportado com sucesso."
            )

        except OSError as erro:
            QMessageBox.critical(self, "Erro", str(erro))
