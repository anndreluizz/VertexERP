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
    QSpinBox,
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
from utils.formatacao import formatar_moeda
from utils.documento_html import (
    ESTILO_BODY,
    bloco_total,
    cabecalho_html,
    cabecalho_tabela,
    linha_zebra,
)
from design.widgets import (
    Avatar,
    Badge,
    BotaoPerigo,
    BotaoPrimario,
    BotaoSecundario,
    BotaoSucesso,
    CampoTexto,
    Card,
    CardKPI,
    DialogoPadrao,
    estilo_botao_forma,
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


class LancarFiadoDialog(DialogoPadrao):
    """Lançamento manual de uma compra fiada — pensado pra migrar o
    saldo que já existia nas fichas de papel (caderninho tradicional),
    onde a loja quer registrar o valor e os itens sem precisar recriar
    a venda inteira no PDV."""

    def __init__(self, cliente, saldo_atual, parent=None):

        super().__init__(
            "Lançar Fiado",
            "Registra uma compra fiada ou uma dívida anterior do cliente.",
            "shopping-cart", tokens.PRIMARIA, tokens.PRIMARIA_CLARA,
            largura=DialogoPadrao.MEDIO, parent=parent,
        )

        self.cliente = cliente
        self._saldo_atual = saldo_atual
        self._tipo_registro = "compra"

        layout = self.corpo

        layout.addWidget(self._construir_cartao_cliente())

        layout.addWidget(self._construir_tipo_registro())

        layout.addLayout(self._construir_linha_valor())

        lbl_itens_titulo = QLabel("Descrição (itens comprados)")
        lbl_itens_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; color:{tokens.TEXTO_SECUNDARIO};
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

        lbl_data_titulo = QLabel("Data da compra")
        lbl_data_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; color:{tokens.TEXTO_SECUNDARIO};
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

        layout.addWidget(self._construir_banner_info(self._texto_banner()))

        layout.addStretch()

        self.bt_confirmar = BotaoSucesso("Lançar Fiado", icone_nome="check")
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.clicked.connect(self.confirmar)
        self.definir_botoes(self.bt_confirmar)

        self.ajustar_altura()
        self.valor.setFocus()

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

        divida = tipo == "divida"
        self.quantidade.setVisible(not divida)
        self.lbl_quantidade.setVisible(not divida)
        self.lbl_valor_titulo.setText("Valor da dívida (R$)" if divida else "Valor unitário (R$)")
        if hasattr(self, "lbl_banner_info"):
            self.lbl_banner_info.setText(self._texto_banner())
        self._atualizar_preview_saldo()

    def _construir_linha_valor(self):

        linha = QHBoxLayout()
        linha.setSpacing(16)

        col_valor = QVBoxLayout()
        col_valor.setSpacing(6)

        linha_titulos = QHBoxLayout()
        linha_titulos.setSpacing(8)

        self.lbl_valor_titulo = QLabel("Valor unitário (R$)")
        self.lbl_valor_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; color:{tokens.TEXTO_SECUNDARIO};
        """)

        self.lbl_quantidade = QLabel("Qtd")
        self.lbl_quantidade.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; color:{tokens.TEXTO_SECUNDARIO};
        """)

        # quantidade x valor unitario = total da compra
        self.quantidade = QSpinBox()
        self.quantidade.setRange(1, 999)
        self.quantidade.setValue(1)
        self.quantidade.setMinimumHeight(32)
        self.quantidade.setMinimumWidth(70)
        self.quantidade.setStyleSheet(f"""
            QSpinBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 6px; font-size: {tokens.TAMANHO_MD}px; font-weight:700;
                color: {tokens.TEXTO}; background: {tokens.CARD};
            }}
            QSpinBox:focus {{ border-color: {tokens.PRIMARIA}; }}
        """)
        self.quantidade.valueChanged.connect(self._atualizar_preview_saldo)

        linha_titulos.addWidget(self.lbl_valor_titulo)
        linha_titulos.addStretch()
        linha_titulos.addWidget(self.lbl_quantidade)
        linha_titulos.addWidget(self.quantidade)

        self.lbl_total_compra = QLabel()
        self.lbl_total_compra.setAlignment(Qt.AlignCenter)
        self.lbl_total_compra.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:700; color:{tokens.TEXTO_SECUNDARIO};
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

        col_valor.addLayout(linha_titulos)
        col_valor.addWidget(self.valor)
        col_valor.addWidget(self.lbl_total_compra)

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

    def _quantidade_atual(self):
        # divida anterior nao tem quantidade (e' um valor total do caderno)
        return 1 if self._tipo_registro == "divida" else self.quantidade.value()

    def _total_digitado(self):
        try:
            unitario = float((self.valor.text() or "0").replace(",", "."))
        except ValueError:
            return None
        return round(unitario * self._quantidade_atual(), 2)

    def _atualizar_preview_saldo(self, _texto=None):

        total = self._total_digitado() or 0.0

        if self._quantidade_atual() > 1:
            self.lbl_total_compra.setText(f"Total da compra: {formatar_moeda(total)}")
        else:
            self.lbl_total_compra.setText("")

        novo_saldo = self._saldo_atual + max(0.0, total)
        self.lbl_preview_novo_saldo.setText(formatar_moeda(novo_saldo))

    def _texto_banner(self):
        if self._tipo_registro == "divida":
            return (
                "Dívida anterior entra só no fiado da cliente (não conta "
                "como venda de hoje)."
            )
        return (
            "Compra fiada conta como venda: aparece em Vendas, no seu "
            "total de vendedora e no faturamento, e entra no fiado da cliente."
        )

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
        self.lbl_banner_info = lbl

        return banner

    def confirmar(self):

        valor = self._total_digitado()

        if valor is None:
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

        quantidade = self._quantidade_atual()
        if quantidade > 1:
            itens = f"{quantidade}x {itens or 'item'}"

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
            registrar_venda=self._tipo_registro == "compra",
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


class RegistrarPagamentoDialog(DialogoPadrao):

    def __init__(self, cliente, saldo_devedor, parent=None):

        super().__init__(
            "Registrar Pagamento",
            "Registra um pagamento do cliente no sistema.",
            "dollar-sign", tokens.SECUNDARIA_HOVER, tokens.SUCESSO_CLARO,
            largura=DialogoPadrao.MEDIO, parent=parent,
        )

        self.cliente = cliente
        self.forma_pagamento = "DINHEIRO"
        self._saldo_devedor = saldo_devedor

        layout = self.corpo

        layout.addWidget(self._construir_cartao_cliente())

        lbl_valor_titulo = QLabel("Valor a pagar (R$)")
        lbl_valor_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; color:{tokens.TEXTO_SECUNDARIO};
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

        lbl_forma_titulo = QLabel("Forma de pagamento")
        lbl_forma_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; color:{tokens.TEXTO_SECUNDARIO};
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
            bt.setMinimumHeight(56)
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

        lbl_obs_titulo = QLabel("Observação (opcional)")
        lbl_obs_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; color:{tokens.TEXTO_SECUNDARIO};
        """)

        self.observacao = CampoTexto("Ex: pagamento parcial, combinado...")

        layout.addWidget(lbl_obs_titulo)
        layout.addWidget(self.observacao)

        lbl_data_titulo = QLabel("Data do pagamento")
        lbl_data_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; color:{tokens.TEXTO_SECUNDARIO};
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

        self.bt_confirmar = BotaoSucesso("Confirmar Pagamento", icone_nome="check")
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.clicked.connect(self.confirmar)
        self.definir_botoes(self.bt_confirmar)

        self.ajustar_altura()
        self.selecionar_forma("DINHEIRO")
        self.valor.setFocus()
        self.valor.selectAll()

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
            estilo, cor_texto = estilo_botao_forma(chave, selecionado)
            botao.setStyleSheet(estilo)
            botao.setIcon(icone(
                _ICONES_FORMA_PAGAMENTO.get(chave, "dollar-sign"),
                cor=cor_texto, tamanho=17,
            ))

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
        corpo.setContentsMargins(28, 4, 28, 12)
        corpo.setSpacing(16)

        coluna_esquerda = QVBoxLayout()
        coluna_esquerda.setSpacing(14)

        coluna_esquerda.addWidget(self._construir_linha_cards())
        coluna_esquerda.addLayout(self._construir_botoes_acao())
        coluna_esquerda.addLayout(self._construir_filtros_timeline())
        coluna_esquerda.addWidget(self._construir_timeline(), stretch=1)

        corpo.addLayout(coluna_esquerda, stretch=2)
        corpo.addWidget(self._construir_painel_lateral())

        raiz.addLayout(corpo, stretch=1)
        raiz.addWidget(self._construir_rodape())

        # sem isso o foco inicial cai no botão WhatsApp (o primeiro da
        # tela), que abre com a moldura de foco desenhada
        self.campo_busca_timeline.setFocus()

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
        """Cabeçalho claro, no mesmo padrão das outras telas (antes era
        uma faixa escura que só existia aqui): avatar, nome com os selos
        de situação e pontuação, telefone e "cliente desde" embaixo, e
        os botões de contato + Editar na ponta direita."""

        cabecalho = QFrame()
        cabecalho.setStyleSheet("background:transparent;")

        layout = QHBoxLayout(cabecalho)
        layout.setContentsMargins(28, 20, 28, 16)
        layout.setSpacing(14)

        self.avatar = Avatar(self.cliente.get("nome", ""), tamanho=48)
        layout.addWidget(self.avatar)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(2)

        linha_nome = QHBoxLayout()
        linha_nome.setSpacing(10)

        self.lbl_titulo = QLabel(self.cliente["nome"])
        self.lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)

        self.badge_ativo = Badge("Ativo", "sucesso")

        # selo de pontuacao (Cliente Ocasional/Frequente/Excelente/...)
        # -- comeca vazio, so' ganha texto/cor em _atualizar_stats
        # (precisa do historico de movimentos, que ainda nao foi
        # buscado nesse ponto da construcao)
        self.badge_pontuacao = Badge("", "info")
        self.badge_pontuacao.setVisible(False)

        linha_nome.addWidget(self.lbl_titulo)
        linha_nome.addWidget(self.badge_ativo, 0, Qt.AlignVCenter)
        linha_nome.addWidget(self.badge_pontuacao, 0, Qt.AlignVCenter)
        linha_nome.addStretch()

        self.lbl_subtitulo = QLabel()
        self.lbl_subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        col_texto.addLayout(linha_nome)
        col_texto.addWidget(self.lbl_subtitulo)

        layout.addLayout(col_texto, stretch=1)

        linha_contato = QHBoxLayout()
        linha_contato.setSpacing(8)

        self.bt_whatsapp = self._botao_contato("WhatsApp", None, "message-circle")
        self.menu_whatsapp = self._construir_menu_whatsapp()
        self.bt_whatsapp.setMenu(self.menu_whatsapp)

        self.bt_ligar = self._botao_contato("Ligar", self.abrir_ligacao)
        self.bt_email = self._botao_contato("E-mail", self.abrir_email, "mail")

        linha_contato.addWidget(self.bt_whatsapp)
        linha_contato.addWidget(self.bt_ligar)
        linha_contato.addWidget(self.bt_email)
        linha_contato.addSpacing(6)

        self.bt_editar_cabecalho = BotaoPrimario("Editar Cliente", icone_nome="edit-2")
        self.bt_editar_cabecalho.setAutoDefault(False)
        self.bt_editar_cabecalho.clicked.connect(self.editar_cliente)
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

    def _botao_contato(self, texto, callback, icone_nome=None):
        """Botão de contato rápido no estilo secundário (fundo claro) --
        ícone só onde existe no pacote Lucide já baixado ('phone' não
        existe, por isso Ligar fica só com texto)."""

        botao = BotaoSecundario(texto, icone_nome=icone_nome)
        botao.setAutoDefault(False)
        if callback:
            botao.clicked.connect(callback)
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


    def _construir_linha_cards(self):
        """4 números grandes numa linha (CardKPI, igual Clientes e
        Contas a Pagar) no lugar dos 10 mini-cards com rótulo de 8px.
        O que sobrou dos mini-cards virou legenda (limite, ticket médio,
        último pagamento) ou foi pro painel Detalhes ao lado. O aviso de
        situação só aparece quando há algo a avisar (atraso, limite)."""

        container = QFrame()
        container.setStyleSheet("background:transparent;")

        layout_externo = QVBoxLayout(container)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        layout_externo.setSpacing(10)

        grade = QGridLayout()
        grade.setSpacing(12)

        self.kpi_saldo = CardKPI("Saldo devedor", "wallet", tokens.PRIMARIA, destaque=True)
        self.kpi_comprado = CardKPI("Total comprado", "shopping-cart", tokens.PRIMARIA)
        self.kpi_pago = CardKPI("Total pago", "check", tokens.SECUNDARIA)
        self.kpi_ultima_compra = CardKPI("Última compra", "calendar", tokens.ALERTA)

        for coluna, card in enumerate((
            self.kpi_saldo, self.kpi_comprado, self.kpi_pago, self.kpi_ultima_compra,
        )):
            grade.addWidget(card, 0, coluna)
            grade.setColumnStretch(coluna, 1)

        layout_externo.addLayout(grade)

        self.lbl_aviso_status = QLabel("")
        self.lbl_aviso_status.setWordWrap(True)
        self.lbl_aviso_status.hide()
        layout_externo.addWidget(self.lbl_aviso_status)

        return container

    def _construir_botoes_acao(self):
        """Uma linha só: as ações do fiado à esquerda (lançar, receber,
        pagamento) e as de documento à direita (extrato, CSV)."""

        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.bt_lancar_fiado = BotaoPerigo("Lançar Fiado", icone_nome="plus")
        self.bt_lancar_fiado.setAutoDefault(False)
        self.bt_lancar_fiado.clicked.connect(self.lancar_fiado)

        self.bt_pagar = BotaoSucesso("Registrar Pagamento", icone_nome="check")
        self.bt_pagar.setAutoDefault(False)
        self.bt_pagar.clicked.connect(self.registrar_pagamento)

        self.bt_extrato = BotaoSecundario("Imprimir Extrato", icone_nome="printer")
        self.bt_extrato.setAutoDefault(False)
        self.bt_extrato.clicked.connect(self.imprimir_extrato)

        self.bt_csv = BotaoSecundario("Exportar CSV", icone_nome="download")
        self.bt_csv.setAutoDefault(False)
        self.bt_csv.clicked.connect(self.exportar_csv)

        layout.addWidget(self.bt_lancar_fiado)
        layout.addWidget(self.bt_pagar)
        layout.addStretch()
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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
            vazio.setWordWrap(True)
            vazio.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_SM}px; padding:8px;
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

        # o backend recusa (403) quem nao tem essa permissao -- nem
        # mostra os botoes pra nao virar um clique que so' da erro
        if api.usuario_tem_permissao("fiado.corrigir"):
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
        """Busca + pílulas de tipo numa linha, no estilo das outras
        telas (Produtos, Contas a Pagar), combinadas na hora de exibir
        (ver _movimentos_filtrados)."""

        layout = QHBoxLayout()
        layout.setSpacing(8)

        self.campo_busca_timeline = CampoTexto("Buscar no histórico...")
        self.campo_busca_timeline.setMinimumWidth(180)
        self.campo_busca_timeline.textChanged.connect(self._on_busca_timeline)
        layout.addWidget(self.campo_busca_timeline, stretch=1)
        layout.addSpacing(4)

        self.botoes_filtro_timeline = {}

        opcoes = [
            ("TODOS", "Todos"),
            ("COMPRA", "Compras"),
            ("PAGAMENTO", "Pagamentos"),
            ("AJUSTES", "Ajustes"),
            ("30DIAS", "30 dias"),
        ]

        for chave, texto in opcoes:
            botao = QPushButton(texto)
            botao.setCheckable(True)
            botao.setCursor(Qt.PointingHandCursor)
            botao.setMinimumHeight(36)
            botao.clicked.connect(lambda _=False, c=chave: self._selecionar_filtro_timeline(c))
            self.botoes_filtro_timeline[chave] = botao
            layout.addWidget(botao)

        self._marcar_filtro_timeline("TODOS")

        return layout

    _ICONES_FILTRO_TIMELINE = {
        "TODOS": "filter", "COMPRA": "shopping-cart", "PAGAMENTO": "dollar-sign",
        "AJUSTES": "refresh-cw", "30DIAS": "calendar",
    }

    def _marcar_filtro_timeline(self, chave):

        self._filtro_timeline = chave

        for k, botao in self.botoes_filtro_timeline.items():
            selecionado = k == chave
            botao.setChecked(selecionado)
            botao.setIcon(icone(
                self._ICONES_FILTRO_TIMELINE.get(k, "filter"),
                cor=tokens.PRIMARIA if selecionado else tokens.TEXTO_SECUNDARIO,
                tamanho=13,
            ))
            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.PRIMARIA_CLARA if selecionado else tokens.CARD};
                    color: {tokens.PRIMARIA if selecionado else tokens.TEXTO_SECUNDARIO};
                    border-radius: 18px;
                    border: 1px solid {tokens.PRIMARIA_CLARA if selecionado else tokens.BORDA};
                    font-weight: {700 if selecionado else 600};
                    font-size: {tokens.TAMANHO_SM}px;
                    padding: 0 12px;
                }}
                QPushButton:hover {{
                    background: {tokens.PRIMARIA_CLARA if selecionado else tokens.FUNDO};
                }}
            """)

    def _selecionar_filtro_timeline(self, chave, _icone_nome=None):

        self._marcar_filtro_timeline(chave)
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
        """Histórico (Compra/Pagamento/Haver/Ajuste) numa lista dentro
        de um card só, com cabeçalho por mês -- mesmo desenho da lista
        de Contas a Pagar. Rolagem própria e incremental (ver
        _verificar_scroll_timeline)."""

        card = Card()
        layout_card = QVBoxLayout(card)
        layout_card.setContentsMargins(1, 1, 1, 1)
        layout_card.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        scroll.verticalScrollBar().valueChanged.connect(
            self._verificar_scroll_timeline
        )

        conteudo = QFrame()
        conteudo.setStyleSheet("background:transparent;")

        self.layout_timeline = QVBoxLayout(conteudo)
        self.layout_timeline.setContentsMargins(0, 0, 0, 0)
        self.layout_timeline.setSpacing(0)
        self.layout_timeline.addStretch()

        scroll.setWidget(conteudo)
        self.scroll_timeline = scroll

        layout_card.addWidget(scroll)

        return card

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

    _MESES = (
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
        "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    )

    def _preencher_timeline(self):

        while self.layout_timeline.count():
            item = self.layout_timeline.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        historico = self._movimentos_filtrados()

        if not historico:
            vazio = QLabel(
                "Nenhuma movimentação encontrada."
                if self._movimentos else
                "Nenhuma movimentação ainda.\nUse Lançar Fiado pra registrar a primeira compra."
            )
            vazio.setAlignment(Qt.AlignCenter)
            vazio.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_BASE}px; padding:32px;
            """)
            self.layout_timeline.addWidget(vazio)
            self.layout_timeline.addStretch()
            return

        visiveis = historico[: self._timeline_qtd_exibida]

        # cabeçalho por mês, com quantidade e saldo do mês (compras -
        # pagamentos) calculados sobre o histórico filtrado inteiro, não
        # só sobre as linhas já montadas
        resumo_mes = {}
        for mov, _saldo in historico:
            chave = self._chave_mes(mov)
            qtd, compras, abatido = resumo_mes.get(chave, (0, 0.0, 0.0))
            valor = float(mov.get("valor", 0) or 0)
            if mov.get("tipo") == "COMPRA":
                compras += valor
            else:
                abatido += valor
            resumo_mes[chave] = (qtd + 1, compras, abatido)

        mes_atual = object()
        for mov, saldo_apos in visiveis:
            chave = self._chave_mes(mov)
            if chave != mes_atual:
                mes_atual = chave
                self.layout_timeline.addWidget(
                    self._cabecalho_mes(chave, *resumo_mes[chave])
                )
            self.layout_timeline.addWidget(self._linha_timeline(mov, saldo_apos))

        texto_contagem = (
            f"Mostrando {len(visiveis)} de {len(historico)} registros — "
            "role pra ver mais"
            if len(historico) > len(visiveis)
            else (
                "1 registro" if len(visiveis) == 1
                else f"{len(visiveis)} registros"
            )
        )
        lbl_mais = QLabel(texto_contagem)
        lbl_mais.setAlignment(Qt.AlignCenter)
        lbl_mais.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; padding:12px;
        """)
        self.layout_timeline.addWidget(lbl_mais)

        self.layout_timeline.addStretch()

    @staticmethod
    def _chave_mes(mov):
        data = _parse_data(mov.get("data"))
        return (data.year, data.month) if data else None

    def _cabecalho_mes(self, chave, qtd, compras, abatido):

        faixa = QFrame()
        faixa.setStyleSheet(f"""
            background:{tokens.FUNDO}; border:none;
            border-bottom:1px solid {tokens.BORDA};
        """)
        layout = QHBoxLayout(faixa)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(10)

        titulo = (
            f"{self._MESES[chave[1] - 1]} de {chave[0]}".upper()
            if chave else "SEM DATA"
        )
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800; letter-spacing:0.5px;
        """)

        partes = [f"{qtd} lançamento{'s' if qtd != 1 else ''}"]
        if compras:
            partes.append(f"comprou {formatar_moeda(compras)}")
        if abatido:
            partes.append(f"pagou {formatar_moeda(abatido)}")
        lbl_resumo = QLabel("  ·  ".join(partes))
        lbl_resumo.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:600;
        """)

        layout.addWidget(lbl_titulo)
        layout.addWidget(lbl_resumo)
        layout.addStretch()

        return faixa

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
        linha.setObjectName("LinhaTimeline")
        linha.setStyleSheet(f"""
            #LinhaTimeline {{
                background:{tokens.CARD}; border:none;
                border-left:3px solid {cor};
                border-bottom:1px solid {tokens.BORDA};
            }}
            #LinhaTimeline:hover {{ background:{tokens.FUNDO}; }}
        """)

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(17, 10, 12, 10)
        layout.setSpacing(12)

        cor_rgb = QColor(cor)
        lbl_icone = QLabel()
        lbl_icone.setFixedSize(32, 32)
        lbl_icone.setAlignment(Qt.AlignCenter)
        lbl_icone.setPixmap(icone_pixmap(icone_nome, cor=cor, tamanho=15))
        lbl_icone.setStyleSheet(f"""
            background: rgba({cor_rgb.red()}, {cor_rgb.green()}, {cor_rgb.blue()}, 0.12);
            border:none; border-radius:{tokens.RADIUS_SM}px;
        """)
        layout.addWidget(lbl_icone)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(2)

        # pagamento/haver costumam vir sem descrição -- aí o próprio
        # tipo vira o título da linha, em vez de uma linha em branco
        descricao = self._descricao_com_itens(mov) or rotulo_tipo
        lbl_descricao = QLabel(descricao)
        lbl_descricao.setWordWrap(True)
        lbl_descricao.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_BASE}px; font-weight:700;
        """)

        data = _parse_data(mov.get("data"))
        partes = [rotulo_tipo, data.strftime("%d/%m/%Y %H:%M") if data else str(mov.get("data") or "")]
        forma = mov.get("forma_pagamento")
        if forma:
            partes.append(NOMES_FORMA_FIADO.get(forma, forma))

        lbl_detalhe = QLabel(
            f'<span style="color:{cor}; font-weight:700;">{partes[0]}</span>'
            f' <span style="color:{tokens.TEXTO_TERCIARIO};">·  {"  ·  ".join(partes[1:])}</span>'
        )
        lbl_detalhe.setTextFormat(Qt.RichText)
        lbl_detalhe.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
        """)

        col_texto.addWidget(lbl_descricao)
        col_texto.addWidget(lbl_detalhe)

        layout.addLayout(col_texto, stretch=1)

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

        lbl_saldo = QLabel(f"saldo {formatar_moeda(saldo_apos)}")
        lbl_saldo.setAlignment(Qt.AlignRight)
        lbl_saldo.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_valor.addWidget(lbl_valor)
        col_valor.addWidget(lbl_saldo)

        layout.addLayout(col_valor)

        layout.addWidget(self._acoes_movimento(mov))

        return linha

    _LARGURA_PAINEL_LATERAL = 290

    def _construir_painel_lateral(self):
        """Painel lateral recolhível: Detalhes (o que não está nos
        números grandes -- cadastro e estatísticas de perfil, em pares
        rótulo/valor como no painel de Clientes), Observações e, no fim,
        as ações raras e perigosas (excluir, LGPD) em tamanho discreto."""

        self.painel_lateral_expandido = True

        wrapper = QFrame()
        wrapper.setStyleSheet("background:transparent;")
        wrapper.setFixedWidth(self._LARGURA_PAINEL_LATERAL)

        layout_wrapper = QVBoxLayout(wrapper)
        layout_wrapper.setContentsMargins(0, 0, 0, 0)
        layout_wrapper.setSpacing(6)

        self.painel_lateral = SecaoCard("Detalhes", "user")

        self.bt_recolher_painel = QPushButton()
        self.bt_recolher_painel.setFixedSize(28, 28)
        self.bt_recolher_painel.setCursor(Qt.PointingHandCursor)
        self.bt_recolher_painel.setIcon(icone("chevron-right", cor=tokens.TEXTO_SECUNDARIO, tamanho=16))
        self.bt_recolher_painel.setToolTip("Recolher o painel de detalhes")
        self.bt_recolher_painel.setAccessibleName("Recolher o painel de detalhes")
        self.bt_recolher_painel.clicked.connect(self._alternar_painel_lateral)
        self.bt_recolher_painel.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)

        self.lbl_resumo_cpf = self._linha_resumo(self.painel_lateral, "CPF/CNPJ")
        self.lbl_resumo_email = self._linha_resumo(self.painel_lateral, "E-mail")
        self.lbl_resumo_endereco = self._linha_resumo(self.painel_lateral, "Endereço")
        self.lbl_resumo_cliente_desde = self._linha_resumo(self.painel_lateral, "Cliente desde")
        self.lbl_resumo_limite = self._linha_resumo(self.painel_lateral, "Limite de crédito")
        self.lbl_resumo_situacao = self._linha_resumo(self.painel_lateral, "Situação")
        self.lbl_resumo_maior_compra = self._linha_resumo(self.painel_lateral, "Maior compra")
        self.lbl_resumo_ticket_medio = self._linha_resumo(self.painel_lateral, "Ticket médio")
        self.lbl_resumo_ultimo_pagamento = self._linha_resumo(self.painel_lateral, "Último pagamento")

        separador = QFrame()
        separador.setFixedHeight(1)
        separador.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        self.painel_lateral.corpo.addSpacing(4)
        self.painel_lateral.corpo.addWidget(separador)

        lbl_obs_titulo = QLabel("OBSERVAÇÕES")
        lbl_obs_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800;
        """)
        self.painel_lateral.corpo.addWidget(lbl_obs_titulo)
        self.painel_lateral.corpo.addWidget(self._construir_pagina_observacoes())

        separador_2 = QFrame()
        separador_2.setFixedHeight(1)
        separador_2.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        self.painel_lateral.corpo.addSpacing(4)
        self.painel_lateral.corpo.addWidget(separador_2)

        self.painel_lateral.corpo.addWidget(
            self._botao_discreto("Excluir cliente", "trash-2", tokens.ERRO, self.excluir_cliente_atual)
        )

        if api.usuario_tem_permissao("clientes.lgpd"):
            self.painel_lateral.corpo.addWidget(self._botao_discreto(
                "Exportar dados (LGPD)", "download", tokens.TEXTO_SECUNDARIO,
                self.exportar_dados_lgpd_atual,
            ))
            self.painel_lateral.corpo.addWidget(self._botao_discreto(
                "Remover dados (LGPD)", "lock", tokens.ERRO, self.remover_dados_lgpd_atual,
            ))

        # o painel inteiro fica dentro da sua própria rolagem vertical --
        # em telas mais baixas (ex.: 1366x768) o conteúdo dele sozinho já
        # passaria da altura do diálogo. Só vertical: a largura é fixa.
        self.scroll_painel_lateral = QScrollArea()
        self.scroll_painel_lateral.setWidgetResizable(True)
        self.scroll_painel_lateral.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_painel_lateral.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }"
        )
        self.scroll_painel_lateral.setWidget(self.painel_lateral)

        linha_toggle = QHBoxLayout()
        linha_toggle.addStretch()
        linha_toggle.addWidget(self.bt_recolher_painel)

        layout_wrapper.addLayout(linha_toggle)
        layout_wrapper.addWidget(self.scroll_painel_lateral, stretch=1)

        self._painel_lateral_wrapper = wrapper
        self._atualizar_detalhes_cadastro(self.cliente)

        return wrapper

    def _botao_discreto(self, texto, icone_nome, cor, callback):

        botao = QPushButton(texto)
        botao.setIcon(icone(icone_nome, cor=cor, tamanho=14))
        botao.setCursor(Qt.PointingHandCursor)
        botao.setAutoDefault(False)
        botao.setMinimumHeight(32)
        botao.clicked.connect(callback)
        botao.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; border-radius:6px;
                color:{cor}; font-size:{tokens.TAMANHO_SM}px; font-weight:600;
                text-align:left; padding:0 8px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        return botao

    def _alternar_painel_lateral(self):

        self.painel_lateral_expandido = not self.painel_lateral_expandido

        self.scroll_painel_lateral.setVisible(self.painel_lateral_expandido)

        if self.painel_lateral_expandido:
            self._painel_lateral_wrapper.setFixedWidth(self._LARGURA_PAINEL_LATERAL)
            self.bt_recolher_painel.setIcon(icone("chevron-right", cor=tokens.TEXTO_SECUNDARIO, tamanho=16))
            self.bt_recolher_painel.setToolTip("Recolher o painel de detalhes")
        else:
            self._painel_lateral_wrapper.setFixedWidth(32)
            self.bt_recolher_painel.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=16))
            self.bt_recolher_painel.setToolTip("Mostrar o painel de detalhes")

    def _linha_resumo(self, secao, titulo):
        """Par rótulo à esquerda / valor à direita, como no painel do
        cliente selecionado em Clientes."""

        linha = QHBoxLayout()
        linha.setSpacing(12)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        lbl_valor = QLabel("—")
        lbl_valor.setWordWrap(True)
        lbl_valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)

        linha.addWidget(lbl_titulo, 0, Qt.AlignTop)
        linha.addWidget(lbl_valor, 1)

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

        partes = [f"Cód. {cliente['id']}" if cliente.get("id") else ""]
        partes.append(cliente.get("telefone") or "Sem telefone")
        cidade = cliente.get("cidade")
        if cidade:
            partes.append(f"{cidade} – {cliente['estado']}" if cliente.get("estado") else cidade)
        self.lbl_subtitulo.setText("  ·  ".join(p for p in partes if p))

        self.bt_whatsapp.setEnabled(bool(cliente.get("telefone")))
        self.bt_ligar.setEnabled(bool(cliente.get("telefone")))
        self.bt_email.setEnabled(bool(cliente.get("email")))

    def _atualizar_detalhes_cadastro(self, cliente):
        """Dados de cadastro no painel Detalhes -- separado de
        _atualizar_cabecalho porque o cabeçalho é montado antes do
        painel existir."""

        self.lbl_resumo_cpf.setText(cliente.get("cpf_cnpj") or "—")
        self.lbl_resumo_email.setText(cliente.get("email") or "—")
        self.lbl_resumo_endereco.setText(cliente.get("endereco") or "—")

        limite = cliente.get("limite_credito")
        self.lbl_resumo_limite.setText(formatar_moeda(limite) if limite else "Sem limite")

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
            self._atualizar_detalhes_cadastro(self.cliente)
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
        # bt_pagar fica de fora -- carregar() decide se ele deveria
        # estar habilitado (saldo > 0) assim que o saldo chegar

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar a ficha do cliente.\n{erro}"
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self.bt_lancar_fiado.setEnabled(True)

    def _ao_carregar_sucesso(self, resultado):

        saldo, self._vendas_por_id, self._nomes_produto, movimentos = resultado

        self.kpi_saldo.definir_valor(formatar_moeda(saldo))

        limite = float(self.cliente.get("limite_credito") or 0)
        if saldo <= 0:
            legenda_saldo = "Nada em aberto"
        elif limite > 0:
            legenda_saldo = f"{saldo / limite:.0%} do limite de {formatar_moeda(limite)}"
        else:
            legenda_saldo = "Sem limite de crédito definido"
        self.kpi_saldo.definir_legenda(legenda_saldo)

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

        def _ha_dias(dias):
            if dias is None:
                return "—"
            if dias == 0:
                return "Hoje"
            if dias == 1:
                return "Ontem"
            return f"Há {dias} dias"

        # números grandes
        self.kpi_comprado.definir_valor(formatar_moeda(total_comprado))
        self.kpi_comprado.definir_legenda(
            f"{qtd_compras} compra{'s' if qtd_compras != 1 else ''}"
            + (f" · média {formatar_moeda(ticket_medio)}" if qtd_compras else "")
        )

        self.kpi_pago.definir_valor(formatar_moeda(total_pago))
        self.kpi_pago.definir_legenda(
            f"último em {_data_curta(agr['ultimo_pagamento'])}"
            if agr["ultimo_pagamento"] else "nenhum pagamento ainda"
        )

        self.kpi_ultima_compra.definir_valor(_ha_dias(agr["dias_desde_ultima_compra"]))
        self.kpi_ultima_compra.definir_legenda(
            _data_curta(agr["ultima_compra"]) if agr["ultima_compra"] else "nenhuma compra ainda"
        )

        pontuacao = cliente_analise.calcular_pontuacao(agr)
        emoji_pont, _, texto_pontuacao = pontuacao.partition(" ")

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

        # aviso só quando há algo a avisar (vermelho/amarelo) -- o verde
        # ("Cliente Ativo") só repetia o selo do cabeçalho
        aviso = cliente_analise.calcular_aviso(agr)
        emoji_aviso, _, texto_aviso = aviso.partition(" ")
        cores_aviso = {
            "🔴": (tokens.ERRO_CLARO, tokens.ERRO),
            "🟡": (tokens.ALERTA_CLARO, tokens.ALERTA),
        }.get(emoji_aviso)

        if cores_aviso:
            cor_fundo, cor_texto = cores_aviso
            self.lbl_aviso_status.setText(texto_aviso or aviso)
            self.lbl_aviso_status.setStyleSheet(f"""
                background:{cor_fundo}; color:{cor_texto}; border:none;
                font-size:{tokens.TAMANHO_SM}px; font-weight:700;
                border-radius:{tokens.RADIUS_SM}px; padding:8px 14px;
            """)
            self.lbl_aviso_status.show()
        else:
            self.lbl_aviso_status.hide()

        # painel Detalhes
        self.lbl_resumo_cliente_desde.setText(_data_curta(agr["criado_em"]))
        self.lbl_resumo_situacao.setText(cliente_analise.status_financeiro(agr))
        self.lbl_resumo_maior_compra.setText(formatar_moeda(maior_compra))
        self.lbl_resumo_ticket_medio.setText(formatar_moeda(ticket_medio))
        self.lbl_resumo_ultimo_pagamento.setText(_data_curta(agr["ultimo_pagamento"]))

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
        self._oferecer_agradecimento(
            f"Muito obrigado pelo seu pagamento de "
            f"{formatar_moeda(dialogo._pagamento_valor_pendente)}!"
        )

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
        self._oferecer_agradecimento(
            f"Muito obrigado pela sua compra de "
            f"{formatar_moeda(dialogo._total_digitado() or 0)}!"
        )

    def _oferecer_agradecimento(self, agradecimento):
        """Depois de um pagamento ou compra no fiado: pergunta se manda
        um obrigado no WhatsApp do cliente, já com o saldo que ficou."""

        if not self.cliente.get("telefone"):
            return

        resposta = QMessageBox.question(
            self, "WhatsApp",
            "Enviar mensagem de agradecimento pro cliente no WhatsApp?",
        )
        if resposta != QMessageBox.Yes:
            return

        saldo = saldo_cliente(self.cliente["id"])
        nome_loja = api.configuracoes().get("nome_loja") or "Vertex ERP"
        restante = (
            f"Saldo restante da sua conta: {formatar_moeda(saldo)}"
            if saldo > 0.009 else "Sua conta está quitada!"
        )

        texto = (
            f"Olá, {self.cliente.get('nome', '')}! Tudo bem?\n\n"
            f"{agradecimento}\n\n"
            f"{restante}\n\n"
            f"Agradecemos a preferência!\n\n"
            f"Equipe {nome_loja}"
        )

        self._enviar_texto_whatsapp(texto, "Agradecimento")

    # ======================================
    # EXTRATO (PDF) / EXPORTAR CSV
    # ======================================

    def _montar_html_extrato(self):

        config = api.configuracoes()

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

            linhas_tabela.append(
                linha_zebra(
                    [data, descricao, debito, credito, formatar_moeda(saldo_apos)],
                    len(linhas_tabela),
                    alinhamentos=["left", "left", "right", "right", "right"],
                )
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
        <body style="{ESTILO_BODY}">
        {cabecalho_html("EXTRATO FINANCEIRO", config)}
        <table width="100%" cellspacing="4">
            <tr><td style="color:#64748B;"><b>Cliente:</b></td><td>{self.cliente.get('nome', '')}</td></tr>
            <tr><td style="color:#64748B;"><b>CPF/CNPJ:</b></td><td>{self.cliente.get('cpf_cnpj') or '—'}</td></tr>
            <tr><td style="color:#64748B;"><b>Telefone:</b></td><td>{self.cliente.get('telefone') or '—'}</td></tr>
            <tr><td style="color:#64748B;"><b>Emitido em:</b></td><td>{agora}</td></tr>
        </table>
        <h4 style="margin:16px 0 6px; color:#1E293B;">MOVIMENTAÇÕES</h4>
        <table style="width:100%; border-collapse:collapse; border:1px solid #E5E7EB;">
            {cabecalho_tabela(
                ["Data", "Descrição", "Débito", "Crédito", "Saldo"],
                ["left", "left", "right", "right", "right"],
            )}
            {linhas_html}
        </table>
        {bloco_observacoes}
        {bloco_total("TOTAL DEVEDOR", formatar_moeda(saldo))}
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
