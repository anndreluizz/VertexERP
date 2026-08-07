import csv
from datetime import date, datetime

from PySide6.QtCore import Qt, QDate, QUrl
from PySide6.QtGui import (
    QColor, QDesktopServices, QFont, QPageSize, QPainter, QPainterPath,
    QPixmap, QTextDocument,
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import (
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
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QInputDialog,
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
)
from telas import comprovante_acoes
from services import cliente_analise

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import (
    Avatar,
    Badge,
    BotaoPerigo,
    BotaoPrimario,
    BotaoSecundario,
    BotaoSucesso,
    CampoTexto,
    Card,
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


def _formatar_moeda(valor):
    return (
        f"R$ {float(valor):,.2f}".replace(",", "X")
        .replace(".", ",").replace("X", ".")
    )


def _parse_data(texto):
    try:
        return datetime.fromisoformat(texto)
    except (ValueError, TypeError):
        return None


class LancarFiadoDialog(QDialog):
    """Lançamento manual de uma compra fiada — pensado pra migrar o
    saldo que já existia nas fichas de papel (caderninho tradicional),
    onde a loja quer registrar o valor e os itens sem precisar recriar
    a venda inteira no PDV."""

    def __init__(self, cliente, parent=None):

        super().__init__(parent)

        self.cliente = cliente

        self.setWindowTitle("Lançar Fiado")
        self.setFixedSize(420, 460)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        titulo = QLabel("Lançar Fiado")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            f"Registra uma compra fiada de {cliente['nome']} — "
            "use pra colocar no sistema o saldo que já estava "
            "anotado na ficha de papel."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(6)

        lbl_valor_titulo = QLabel("VALOR (R$)")
        lbl_valor_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.valor = QLineEdit()
        self.valor.setPlaceholderText("0,00")
        self.valor.setAlignment(Qt.AlignCenter)
        self.valor.setStyleSheet(f"""
            QLineEdit {{
                font-size:32px; font-weight:800; color:{tokens.ERRO};
                border:none; border-bottom:2px solid {tokens.BORDA};
                padding:6px 0; background:transparent;
            }}
        """)

        layout.addWidget(lbl_valor_titulo)
        layout.addWidget(self.valor)

        lbl_itens_titulo = QLabel("DESCRIÇÃO (ITENS COMPRADOS)")
        lbl_itens_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.itens = CampoTexto("Ex: mochila, caderno")

        layout.addWidget(lbl_itens_titulo)
        layout.addWidget(self.itens)

        lbl_data_titulo = QLabel("DATA DA COMPRA")
        lbl_data_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.data = QDateEdit()
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        self.data.setDate(QDate.currentDate())
        self.data.setMinimumHeight(44)
        self.data.setStyleSheet(f"""
            QDateEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
            }}
            QDateEdit:focus {{ border: 1.5px solid {tokens.ERRO}; }}
        """)

        layout.addWidget(lbl_data_titulo)
        layout.addWidget(self.data)

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        bt_confirmar = BotaoPerigo("Salvar")
        bt_confirmar.setMinimumHeight(46)
        bt_confirmar.setAutoDefault(False)
        bt_confirmar.clicked.connect(self.confirmar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(bt_confirmar)

        layout.addLayout(botoes)

        self.valor.setFocus()

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

        limite = self.cliente.get("limite_credito")

        if limite is not None:

            saldo_atual = saldo_cliente(self.cliente["id"])
            saldo_projetado = saldo_atual + valor

            if saldo_projetado > limite:

                resposta = QMessageBox.warning(
                    self,
                    "Limite de crédito",
                    f"Esse lançamento deixa o saldo devedor em "
                    f"{_formatar_moeda(saldo_projetado)}, acima do limite "
                    f"de crédito cadastrado ({_formatar_moeda(limite)}).\n\n"
                    "Deseja lançar mesmo assim?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )

                if resposta != QMessageBox.Yes:
                    return

        itens = self.itens.text().strip() or None

        data_qt = self.data.date()
        data_iso = (
            date(data_qt.year(), data_qt.month(), data_qt.day())
            .isoformat()
            + "T00:00:00"
        )

        response = lancar_fiado_manual(
            self.cliente["id"], valor, itens, data_iso
        )

        if response.status_code in (200, 201):
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))


class RegistrarPagamentoDialog(QDialog):

    def __init__(self, cliente, saldo_devedor, parent=None):

        super().__init__(parent)

        self.cliente = cliente
        self.forma_pagamento = "DINHEIRO"

        self.setWindowTitle("Registrar Pagamento")
        self.setFixedSize(420, 560)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        titulo = QLabel("Registrar Pagamento")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            f"Saldo devedor de {cliente['nome']}: "
            f"{_formatar_moeda(saldo_devedor)}"
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(6)

        lbl_valor_titulo = QLabel("VALOR A PAGAR (R$)")
        lbl_valor_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.valor = QLineEdit()
        self.valor.setText(f"{saldo_devedor:.2f}")
        self.valor.setAlignment(Qt.AlignCenter)
        self.valor.setStyleSheet(f"""
            QLineEdit {{
                font-size:32px; font-weight:800; color:{tokens.SECUNDARIA};
                border:none; border-bottom:2px solid {tokens.BORDA};
                padding:6px 0; background:transparent;
            }}
        """)

        layout.addWidget(lbl_valor_titulo)
        layout.addWidget(self.valor)

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
            bt.setMinimumHeight(44)
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

        self.data = QDateEdit()
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        self.data.setDate(QDate.currentDate())
        self.data.setMinimumHeight(44)
        self.data.setStyleSheet(f"""
            QDateEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
            }}
            QDateEdit:focus {{ border: 1.5px solid {tokens.SECUNDARIA}; }}
        """)

        layout.addWidget(lbl_data_titulo)
        layout.addWidget(self.data)

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        self.bt_confirmar = BotaoSucesso("Confirmar")
        self.bt_confirmar.setMinimumHeight(46)
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.clicked.connect(self.confirmar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(self.bt_confirmar)

        layout.addLayout(botoes)

        self.selecionar_forma("DINHEIRO")

    def selecionar_forma(self, valor):

        self.forma_pagamento = valor

        for chave, botao in self.botoes_forma.items():

            selecionado = chave == valor

            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.SECUNDARIA if selecionado else tokens.FUNDO};
                    color: {"white" if selecionado else tokens.TEXTO};
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

        response = registrar_pagamento(
            self.cliente["id"],
            valor,
            self.forma_pagamento,
            descricao=self.observacao.text().strip() or None,
            data=data_iso,
        )

        if response.status_code in (200, 201):
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))


class FichaClienteDialog(QDialog):

    def __init__(self, cliente, parent=None):

        super().__init__(parent)

        self.cliente = cliente
        self._vendas_por_id = {}
        self._nomes_produto = {}
        self._movimentos = []

        self.setWindowTitle(f"Ficha - {cliente['nome']}")
        self.resize(960, 720)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        raiz.addWidget(self._construir_cabecalho())

        corpo = QHBoxLayout()
        corpo.setContentsMargins(24, 20, 24, 16)
        corpo.setSpacing(16)

        coluna_esquerda = QVBoxLayout()
        coluna_esquerda.setSpacing(16)

        coluna_esquerda.addWidget(self._construir_card_financeiro())
        coluna_esquerda.addLayout(self._construir_botoes_acao())
        coluna_esquerda.addWidget(self._construir_abas(), stretch=1)

        corpo.addLayout(coluna_esquerda, stretch=2)
        corpo.addWidget(self._construir_painel_lateral())

        raiz.addLayout(corpo, stretch=1)
        raiz.addWidget(self._construir_rodape())

        self.carregar()

    # ======================================
    # CONSTRUÇÃO DA INTERFACE
    # ======================================

    def _construir_cabecalho(self):

        cabecalho = QFrame()
        cabecalho.setStyleSheet(f"background:{tokens.SIDEBAR};")

        layout = QHBoxLayout(cabecalho)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(16)

        self.avatar = Avatar(self.cliente.get("nome", ""), tamanho=56)
        layout.addWidget(self.avatar)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(2)

        linha_nome = QHBoxLayout()
        linha_nome.setSpacing(10)

        self.lbl_titulo = QLabel(self.cliente["nome"])
        self.lbl_titulo.setStyleSheet(f"""
            background:transparent; color:white;
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)

        self.badge_ativo = Badge("Ativo", "sucesso")

        linha_nome.addWidget(self.lbl_titulo)
        linha_nome.addWidget(self.badge_ativo, 0)
        linha_nome.addStretch()

        self.lbl_subtitulo = QLabel()
        self.lbl_subtitulo.setWordWrap(True)
        self.lbl_subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        col_texto.addLayout(linha_nome)
        col_texto.addWidget(self.lbl_subtitulo)

        linha_contato = QHBoxLayout()
        linha_contato.setSpacing(8)

        self.bt_whatsapp = self._botao_contato("WhatsApp", self.abrir_whatsapp)
        self.bt_ligar = self._botao_contato("Ligar", self.abrir_ligacao)
        self.bt_email = self._botao_contato("E-mail", self.abrir_email)
        self.bt_mapa = self._botao_contato("Mapa", self.abrir_mapa)

        linha_contato.addWidget(self.bt_whatsapp)
        linha_contato.addWidget(self.bt_ligar)
        linha_contato.addWidget(self.bt_email)
        linha_contato.addWidget(self.bt_mapa)
        linha_contato.addStretch()

        col_texto.addSpacing(6)
        col_texto.addLayout(linha_contato)

        layout.addLayout(col_texto, stretch=1)

        self._atualizar_cabecalho(self.cliente)
        self._atualizar_avatar(self.cliente)

        return cabecalho

    def _botao_contato(self, texto, callback):
        """Botão de contato rápido só com texto (sem ícone) — os ícones
        'phone'/'map-pin' não existem no pacote Lucide já baixado, e a
        decisão foi não baixar novos ícones pra isso. Estilo "vidro"
        sobre o fundo escuro do cabeçalho, já que o BotaoSecundario
        padrão foi desenhado pra fundo claro."""

        botao = QPushButton(texto)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setFixedHeight(28)
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

    def abrir_whatsapp(self):

        digitos = self._telefone_digitos()

        if not digitos:
            return

        if len(digitos) <= 11:
            digitos = "55" + digitos

        QDesktopServices.openUrl(QUrl(f"https://wa.me/{digitos}"))

    def abrir_ligacao(self):

        digitos = self._telefone_digitos()

        if digitos:
            QDesktopServices.openUrl(QUrl(f"tel:{digitos}"))

    def abrir_email(self):

        email = self.cliente.get("email")

        if email:
            QDesktopServices.openUrl(QUrl(f"mailto:{email}"))

    def abrir_mapa(self):

        from urllib.parse import quote

        partes = [
            self.cliente.get("endereco"),
            self.cliente.get("cidade"),
            self.cliente.get("estado"),
        ]
        endereco = ", ".join(p for p in partes if p)

        if not endereco:
            return

        QDesktopServices.openUrl(
            QUrl(f"https://www.google.com/maps/search/?api=1&query={quote(endereco)}")
        )

    def _construir_card_financeiro(self):

        self.card_financeiro = Card()

        layout_externo = QVBoxLayout(self.card_financeiro)
        layout_externo.setContentsMargins(22, 18, 22, 18)
        layout_externo.setSpacing(14)

        linha_principal = QHBoxLayout()
        linha_principal.setSpacing(28)

        col_saldo = QVBoxLayout()
        col_saldo.setSpacing(2)

        lbl_saldo_titulo = QLabel("SALDO DEVEDOR (FIADO)")
        lbl_saldo_titulo.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.lbl_saldo_valor = QLabel("R$ 0,00")
        self.lbl_saldo_valor.setStyleSheet(f"""
            background:transparent; border:none; font-size:32px;
            font-weight:800; color:{tokens.ERRO};
        """)

        self.lbl_saldo_info = QLabel("")
        self.lbl_saldo_info.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col_saldo.addWidget(lbl_saldo_titulo)
        col_saldo.addWidget(self.lbl_saldo_valor)
        col_saldo.addWidget(self.lbl_saldo_info)

        linha_principal.addLayout(col_saldo)

        linha = QFrame()
        linha.setFixedWidth(1)
        linha.setStyleSheet(f"background:{tokens.BORDA};")
        linha_principal.addWidget(linha)

        grid_stats = QGridLayout()
        grid_stats.setHorizontalSpacing(28)
        grid_stats.setVerticalSpacing(6)

        self.lbl_total_comprado = self._stat_pequena(
            grid_stats, 0, 0, "TOTAL COMPRADO"
        )
        self.lbl_qtd_compras = self._stat_pequena(
            grid_stats, 0, 1, "QTD. COMPRAS"
        )
        self.lbl_ultima_compra = self._stat_pequena(
            grid_stats, 0, 2, "ÚLTIMA COMPRA"
        )
        self.lbl_ultimo_pagamento = self._stat_pequena(
            grid_stats, 1, 0, "ÚLTIMO PAGAMENTO"
        )
        self.lbl_ultimo_movimento = self._stat_pequena(
            grid_stats, 1, 1, "ÚLTIMO MOVIMENTO"
        )
        self.lbl_dias_sem_movimentacao = self._stat_pequena(
            grid_stats, 1, 2, "DIAS SEM MOVIMENTAÇÃO"
        )
        self.lbl_dias_desde_ultima_compra = self._stat_pequena(
            grid_stats, 2, 0, "DIAS DESDE ÚLTIMA COMPRA"
        )
        self.lbl_dias_desde_ultimo_pagamento = self._stat_pequena(
            grid_stats, 2, 1, "DIAS DESDE ÚLTIMO PAGAMENTO"
        )
        self.lbl_cliente_desde = self._stat_pequena(
            grid_stats, 2, 2, "CLIENTE DESDE"
        )
        self.lbl_status_financeiro = self._stat_pequena(
            grid_stats, 3, 0, "STATUS FINANCEIRO"
        )
        self.lbl_status_relacionamento = self._stat_pequena(
            grid_stats, 3, 1, "STATUS DE RELACIONAMENTO"
        )
        self.lbl_score = self._stat_pequena(
            grid_stats, 3, 2, "PONTUAÇÃO"
        )

        linha_principal.addLayout(grid_stats, stretch=1)

        layout_externo.addLayout(linha_principal)

        self.lbl_aviso_status = QLabel("")
        self.lbl_aviso_status.setAlignment(Qt.AlignCenter)
        self.lbl_aviso_status.setWordWrap(True)
        layout_externo.addWidget(self.lbl_aviso_status)

        return self.card_financeiro

    def _stat_pequena(self, grid, linha, coluna, titulo):

        col = QVBoxLayout()
        col.setSpacing(0)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        lbl_valor = QLabel("—")
        lbl_valor.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_MD}px;
            font-weight:700; color:{tokens.TEXTO};
        """)

        col.addWidget(lbl_titulo)
        col.addWidget(lbl_valor)

        grid.addLayout(col, linha, coluna)

        return lbl_valor

    def _construir_botoes_acao(self):

        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.bt_lancar_fiado = BotaoPerigo("Lançar Fiado", icone_nome="plus")
        self.bt_lancar_fiado.setMinimumHeight(46)
        self.bt_lancar_fiado.setAutoDefault(False)
        self.bt_lancar_fiado.clicked.connect(self.lancar_fiado)

        self.bt_pagar = BotaoSucesso("Registrar Pagamento", icone_nome="check")
        self.bt_pagar.setMinimumHeight(46)
        self.bt_pagar.setAutoDefault(False)
        self.bt_pagar.clicked.connect(self.registrar_pagamento)

        self.bt_extrato = BotaoSecundario("Imprimir Extrato", icone_nome="printer")
        self.bt_extrato.setMinimumHeight(46)
        self.bt_extrato.setAutoDefault(False)
        self.bt_extrato.clicked.connect(self.imprimir_extrato)

        self.bt_csv = BotaoSecundario("Exportar CSV", icone_nome="download")
        self.bt_csv.setMinimumHeight(46)
        self.bt_csv.setAutoDefault(False)
        self.bt_csv.clicked.connect(self.exportar_csv)

        self.bt_ultimo_comprovante = BotaoSecundario(
            "Enviar Último Comprovante", icone_nome="message-circle"
        )
        self.bt_ultimo_comprovante.setMinimumHeight(46)
        self.bt_ultimo_comprovante.setAutoDefault(False)
        self.bt_ultimo_comprovante.clicked.connect(
            self.enviar_ultimo_comprovante
        )

        layout.addWidget(self.bt_lancar_fiado)
        layout.addWidget(self.bt_pagar)
        layout.addStretch()
        layout.addWidget(self.bt_ultimo_comprovante)
        layout.addWidget(self.bt_extrato)
        layout.addWidget(self.bt_csv)

        return layout

    def enviar_ultimo_comprovante(self):

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

        data = str(ultima_venda["data"]).replace("T", " ")[:16]

        resposta = QMessageBox.question(
            self,
            "Enviar Último Comprovante",
            f"Enviar pelo WhatsApp o comprovante da venda #{ultima_venda['id']}"
            f" ({data}, R$ {float(ultima_venda['valor_total']):.2f})?",
        )

        if resposta != QMessageBox.Yes:
            return

        comprovante_acoes.enviar_whatsapp(ultima_venda["id"], self)

    def _construir_abas(self):

        container = QFrame()
        container.setStyleSheet("background:transparent;")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        abas_layout = QHBoxLayout()
        abas_layout.setSpacing(24)

        self.bt_aba_historico = self._botao_aba("Histórico Financeiro")
        self.bt_aba_compras = self._botao_aba("Compras")
        self.bt_aba_pagamentos = self._botao_aba("Pagamentos")
        self.bt_aba_observacoes = self._botao_aba("Observações")

        self.bt_aba_historico.clicked.connect(lambda: self._selecionar_aba(0))
        self.bt_aba_compras.clicked.connect(lambda: self._selecionar_aba(1))
        self.bt_aba_pagamentos.clicked.connect(lambda: self._selecionar_aba(2))
        self.bt_aba_observacoes.clicked.connect(lambda: self._selecionar_aba(3))

        self.botoes_aba = [
            self.bt_aba_historico,
            self.bt_aba_compras,
            self.bt_aba_pagamentos,
            self.bt_aba_observacoes,
        ]

        for botao in self.botoes_aba:
            abas_layout.addWidget(botao)

        abas_layout.addStretch()

        layout.addLayout(abas_layout)

        linha_abas = QFrame()
        linha_abas.setFixedHeight(1)
        linha_abas.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(linha_abas)

        layout.addSpacing(12)

        self.pagina_historico = self._construir_timeline()
        self.tabela_compras = self._construir_tabela()
        self.tabela_pagamentos = self._construir_tabela()
        self.pagina_observacoes = self._construir_pagina_observacoes()

        self.paginas_aba = [
            self.pagina_historico,
            self.tabela_compras,
            self.tabela_pagamentos,
            self.pagina_observacoes,
        ]

        for pagina in self.paginas_aba:
            layout.addWidget(pagina, stretch=1)

        self._selecionar_aba(0)

        return container

    def _botao_aba(self, texto):

        botao = QPushButton(texto)
        botao.setCheckable(True)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:700; padding-bottom:10px;
            }}
            QPushButton:checked {{
                color:{tokens.PRIMARIA}; border-bottom:2px solid {tokens.PRIMARIA};
            }}
        """)
        return botao

    def _selecionar_aba(self, indice):

        for i, botao in enumerate(self.botoes_aba):
            botao.setChecked(i == indice)

        for i, pagina in enumerate(self.paginas_aba):
            pagina.setVisible(i == indice)

    def _construir_pagina_observacoes(self):

        pagina = QFrame()
        pagina.setStyleSheet("background:transparent;")

        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        linha_nova = QHBoxLayout()
        linha_nova.setSpacing(8)

        self.campo_nova_observacao = CampoTexto(
            "Escreva uma observação sobre o cliente..."
        )

        bt_adicionar = BotaoPrimario("Adicionar")
        bt_adicionar.setFixedHeight(44)
        bt_adicionar.setAutoDefault(False)
        bt_adicionar.clicked.connect(self.adicionar_observacao)

        linha_nova.addWidget(self.campo_nova_observacao, stretch=1)
        linha_nova.addWidget(bt_adicionar)

        layout.addLayout(linha_nova)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        conteudo = QFrame()
        conteudo.setStyleSheet("background:transparent;")

        self.layout_observacoes = QVBoxLayout(conteudo)
        self.layout_observacoes.setContentsMargins(0, 0, 6, 0)
        self.layout_observacoes.setSpacing(8)
        self.layout_observacoes.addStretch()

        scroll.setWidget(conteudo)
        layout.addWidget(scroll, stretch=1)

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
        observacoes = listar_observacoes_cliente(self.cliente["id"])
        self._preencher_observacoes(observacoes)

    def adicionar_observacao(self):

        texto = self.campo_nova_observacao.text().strip()

        if not texto:
            return

        response = criar_observacao_cliente(self.cliente["id"], texto)

        if response.status_code in (200, 201):
            self.campo_nova_observacao.clear()
            self._carregar_observacoes()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def excluir_observacao(self, observacao_id):

        resposta = QMessageBox.question(
            self, "Excluir Observação", "Deseja excluir esta observação?"
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_observacao_cliente(self.cliente["id"], observacao_id)

        if response.status_code == 200:
            self._carregar_observacoes()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _construir_tabela(self):

        tabela = QTableWidget()
        tabela.setColumnCount(7)
        tabela.setHorizontalHeaderLabels(
            ["", "Data", "Descrição", "Forma Pagamento", "Valor", "Saldo Após", ""]
        )
        tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        tabela.setColumnWidth(0, 36)
        tabela.setColumnWidth(1, 140)
        tabela.setColumnWidth(3, 140)
        tabela.setColumnWidth(4, 110)
        tabela.setColumnWidth(5, 110)
        tabela.setColumnWidth(6, 70)
        tabela.verticalHeader().setVisible(False)
        tabela.verticalHeader().setDefaultSectionSize(38)
        tabela.setAlternatingRowColors(True)
        tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        tabela.setSelectionMode(QTableWidget.NoSelection)
        tabela.setFocusPolicy(Qt.NoFocus)
        tabela.setShowGrid(False)
        tabela.setStyleSheet(f"""
            QTableWidget {{
                background:{tokens.CARD};
                alternate-background-color:{tokens.FUNDO};
                border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_MD}px;
                color:{tokens.TEXTO};
                font-size:{tokens.TAMANHO_BASE}px;
            }}
            QTableWidget::item {{
                background:transparent;
            }}
            QHeaderView::section {{
                background:{tokens.FUNDO};
                color:{tokens.TEXTO_SECUNDARIO};
                padding:8px;
                border:none;
                border-bottom:1px solid {tokens.BORDA};
                font-weight:700;
                font-size:{tokens.TAMANHO_XS}px;
            }}
        """)

        return tabela

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

        response = editar_movimento(mov["id"], valor=novo_valor)

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

    def _excluir_movimento_fiado(self, mov):

        resposta = QMessageBox.question(
            self,
            "Excluir Lançamento",
            "Excluir este lançamento do fiado? Essa ação não pode ser desfeita.",
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_movimento(mov["id"])

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

    def _construir_timeline(self):
        """Aba 'Histórico Financeiro' como linha do tempo vertical, em
        vez de tabela — os dados já vêm calculados cronologicamente
        (ver carregar()), isso só troca a forma de exibir."""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        conteudo = QFrame()
        conteudo.setStyleSheet("background:transparent;")

        self.layout_timeline = QVBoxLayout(conteudo)
        self.layout_timeline.setContentsMargins(0, 0, 6, 0)
        self.layout_timeline.setSpacing(8)
        self.layout_timeline.addStretch()

        scroll.setWidget(conteudo)

        return scroll

    def _preencher_timeline(self, historico):

        while self.layout_timeline.count():
            item = self.layout_timeline.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not historico:
            vazio = QLabel("Nenhuma movimentação registrada ainda.")
            vazio.setAlignment(Qt.AlignCenter)
            vazio.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_BASE}px; padding:20px;
            """)
            self.layout_timeline.addWidget(vazio)
            self.layout_timeline.addStretch()
            return

        for mov, saldo_apos in historico:
            self.layout_timeline.addWidget(self._linha_timeline(mov, saldo_apos))

        self.layout_timeline.addStretch()

    def _linha_timeline(self, mov, saldo_apos):

        tipo = mov.get("tipo", "")
        estorno = self._e_estorno(mov)

        if estorno:
            cor = tokens.ERRO
            icone_nome = "refresh-cw"
        elif tipo == "COMPRA":
            cor = tokens.PRIMARIA
            icone_nome = "shopping-cart"
        else:
            cor = tokens.SECUNDARIA
            icone_nome = "check"

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

        lbl_data = QLabel(data)
        lbl_data.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        lbl_descricao = QLabel(self._descricao_com_itens(mov))
        lbl_descricao.setWordWrap(True)
        lbl_descricao.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:600;
        """)

        col_texto.addWidget(lbl_data)
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
            f"+ {_formatar_moeda(valor)}"
            if tipo == "COMPRA"
            else f"- {_formatar_moeda(valor)}"
        )

        lbl_valor = QLabel(texto_valor)
        lbl_valor.setAlignment(Qt.AlignRight)
        lbl_valor.setStyleSheet(f"""
            background:transparent; border:none; color:{cor};
            font-size:{tokens.TAMANHO_MD}px; font-weight:800;
        """)

        lbl_saldo = QLabel(f"Saldo: {_formatar_moeda(saldo_apos)}")
        lbl_saldo.setAlignment(Qt.AlignRight)
        lbl_saldo.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_valor.addWidget(lbl_valor)
        col_valor.addWidget(lbl_saldo)

        layout.addLayout(col_valor)

        return linha

    def _construir_painel_lateral(self):

        self.painel_lateral = SecaoCard("Resumo", "bar-chart-2")
        self.painel_lateral.setFixedWidth(260)

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

        self.painel_lateral.corpo.addStretch()

        return self.painel_lateral

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

        rodape = QFrame()
        rodape.setStyleSheet(f"""
            background:{tokens.CARD}; border-top:1px solid {tokens.BORDA};
        """)

        layout = QHBoxLayout(rodape)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(10)

        bt_editar = BotaoPrimario("Editar Cliente", icone_nome="edit-2")
        bt_editar.setMinimumHeight(42)
        bt_editar.setAutoDefault(False)
        bt_editar.clicked.connect(self.editar_cliente)

        bt_excluir = BotaoPerigo("Excluir", icone_nome="trash-2")
        bt_excluir.setMinimumHeight(42)
        bt_excluir.setAutoDefault(False)
        bt_excluir.clicked.connect(self.excluir_cliente_atual)

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.setMinimumHeight(42)
        bt_fechar.setAutoDefault(False)
        bt_fechar.clicked.connect(self.accept)

        layout.addWidget(bt_editar)
        layout.addWidget(bt_excluir)
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
        fundo, cor_texto = Badge.VARIANTES[variante]
        self.badge_ativo.setStyleSheet(f"""
            background: {fundo}; color: {cor_texto};
            border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
            font-weight: 600; padding: 3px 10px;
        """)

        detalhes = " · ".join(
            filter(
                None,
                [
                    cliente.get("telefone"),
                    cliente.get("cpf_cnpj"),
                    cliente.get("endereco"),
                ],
            )
        ) or "Sem dados de contato"

        self.lbl_subtitulo.setText(detalhes)

        self.bt_whatsapp.setEnabled(bool(cliente.get("telefone")))
        self.bt_ligar.setEnabled(bool(cliente.get("telefone")))
        self.bt_email.setEnabled(bool(cliente.get("email")))
        self.bt_mapa.setEnabled(bool(cliente.get("endereco")))

    def _atualizar_avatar(self, cliente):

        if not cliente.get("tem_foto"):
            return

        foto_bytes = obter_foto_cliente(cliente["id"])

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

        response = excluir_cliente(self.cliente["id"])

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

        saldo = saldo_cliente(self.cliente["id"])

        self.lbl_saldo_valor.setText(_formatar_moeda(saldo))
        self.lbl_saldo_valor.setStyleSheet(f"""
            background:transparent; border:none; font-size:32px;
            font-weight:800;
            color:{tokens.ERRO if saldo > 0 else tokens.SECUNDARIA};
        """)

        self.bt_pagar.setEnabled(saldo > 0)

        self._vendas_por_id = {
            v["id"]: v for v in listar_vendas()
        }
        self._nomes_produto = {
            p["id"]: p["nome"] for p in listar_produtos()
        }

        movimentos = listar_movimentos_cliente(self.cliente["id"])

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

        self._preencher_timeline(historico_calculado)
        self._preencher_tabela(
            self.tabela_compras,
            [h for h in historico_calculado if h[0].get("tipo") == "COMPRA"],
        )
        self._preencher_tabela(
            self.tabela_pagamentos,
            [h for h in historico_calculado if h[0].get("tipo") == "PAGAMENTO"],
        )

        self._atualizar_stats(movimentos_cron, saldo)
        self._carregar_observacoes()

    def _preencher_tabela(self, tabela, historico):

        tabela.setRowCount(len(historico))

        for linha, (mov, saldo_apos) in enumerate(historico):

            tipo = mov.get("tipo", "")
            estorno = self._e_estorno(mov)

            if estorno:
                cor = tokens.ERRO
                icone_nome = "refresh-cw"
            elif tipo == "COMPRA":
                cor = tokens.PRIMARIA
                icone_nome = "shopping-cart"
            else:
                cor = tokens.SECUNDARIA
                icone_nome = "check"

            item_icone = QTableWidgetItem()
            item_icone.setIcon(icone(icone_nome, cor=cor, tamanho=16))
            tabela.setItem(linha, 0, item_icone)

            data = str(mov.get("data", ""))
            if "T" in data:
                data = data.replace("T", " ")

            item_data = QTableWidgetItem(data[:19])
            item_data.setForeground(QColor(cor))
            tabela.setItem(linha, 1, item_data)

            item_descricao = QTableWidgetItem(self._descricao_com_itens(mov))
            item_descricao.setForeground(QColor(tokens.TEXTO))
            tabela.setItem(linha, 2, item_descricao)

            forma = mov.get("forma_pagamento")
            texto_forma = NOMES_FORMA_FIADO.get(forma, forma) if forma else "—"
            item_forma = QTableWidgetItem(texto_forma)
            item_forma.setForeground(QColor(tokens.TEXTO_SECUNDARIO))
            tabela.setItem(linha, 3, item_forma)

            valor = float(mov.get("valor", 0) or 0)
            texto_valor = (
                f"+ {_formatar_moeda(valor)}"
                if tipo == "COMPRA"
                else f"- {_formatar_moeda(valor)}"
            )
            item_valor = QTableWidgetItem(texto_valor)
            item_valor.setForeground(QColor(cor))
            tabela.setItem(linha, 4, item_valor)

            item_saldo = QTableWidgetItem(_formatar_moeda(saldo_apos))
            item_saldo.setForeground(QColor(tokens.TEXTO))
            tabela.setItem(linha, 5, item_saldo)

            tabela.setCellWidget(linha, 6, self._acoes_movimento(mov))

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

        # card financeiro
        self.lbl_total_comprado.setText(_formatar_moeda(total_comprado))
        self.lbl_qtd_compras.setText(str(qtd_compras))
        self.lbl_ultima_compra.setText(_data_curta(agr["ultima_compra"]))
        self.lbl_ultimo_pagamento.setText(_data_curta(agr["ultimo_pagamento"]))
        self.lbl_ultimo_movimento.setText(_data_curta(agr["ultima_movimentacao"]))
        self.lbl_dias_sem_movimentacao.setText(
            _dias_texto(agr["dias_sem_movimentacao"])
        )
        self.lbl_dias_desde_ultima_compra.setText(
            _dias_texto(agr["dias_desde_ultima_compra"])
        )
        self.lbl_dias_desde_ultimo_pagamento.setText(
            _dias_texto(agr["dias_desde_ultimo_pagamento"])
        )
        self.lbl_cliente_desde.setText(_data_curta(agr["criado_em"]))

        self.lbl_status_financeiro.setText(
            cliente_analise.status_financeiro(agr)
        )
        self.lbl_status_relacionamento.setText(
            cliente_analise.status_relacionamento(agr)
        )
        self.lbl_score.setText(cliente_analise.calcular_pontuacao(agr))

        aviso = cliente_analise.calcular_aviso(agr)
        cor_fundo, cor_texto = {
            "🔴": (tokens.ERRO_CLARO, tokens.ERRO),
            "🟡": (tokens.ALERTA_CLARO, tokens.ALERTA),
            "🟢": (tokens.SUCESSO_CLARO, tokens.SECUNDARIA_HOVER),
        }.get(aviso[:1], (tokens.FUNDO, tokens.TEXTO_SECUNDARIO))

        self.lbl_aviso_status.setText(aviso)
        self.lbl_aviso_status.setStyleSheet(f"""
            background:{cor_fundo}; color:{cor_texto}; border:none;
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            border-radius:{tokens.RADIUS_SM}px; padding:6px 10px;
        """)

        if saldo_atual > 0 and agr["dias_sem_movimentacao"] is not None:
            dias = agr["dias_sem_movimentacao"]
            self.lbl_saldo_info.setText(
                f"Última movimentação há {dias} dia(s)"
                if dias > 0 else "Movimentação de hoje"
            )
        else:
            self.lbl_saldo_info.setText("")

        # painel lateral
        self.lbl_resumo_total_comprado.setText(_formatar_moeda(total_comprado))
        self.lbl_resumo_total_pago.setText(_formatar_moeda(total_pago))
        self.lbl_resumo_saldo_atual.setText(_formatar_moeda(saldo_atual))
        self.lbl_resumo_maior_compra.setText(_formatar_moeda(maior_compra))
        self.lbl_resumo_ultima_compra.setText(_data_curta(agr["ultima_compra"]))
        self.lbl_resumo_ticket_medio.setText(_formatar_moeda(ticket_medio))
        self.lbl_resumo_total_compras.setText(str(qtd_compras))

    def registrar_pagamento(self):

        saldo = saldo_cliente(self.cliente["id"])

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

        dialogo = LancarFiadoDialog(self.cliente, parent=self)

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

            debito = _formatar_moeda(valor) if tipo == "COMPRA" else ""
            credito = _formatar_moeda(valor) if tipo == "PAGAMENTO" else ""

            linhas_tabela.append(
                f"<tr>"
                f"<td>{data}</td>"
                f"<td>{descricao}</td>"
                f"<td align='right'>{debito}</td>"
                f"<td align='right'>{credito}</td>"
                f"<td align='right'>{_formatar_moeda(saldo_apos)}</td>"
                f"</tr>"
            )

        linhas_html = "".join(linhas_tabela) or (
            "<tr><td colspan='5' align='center'>"
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
        <div style="text-align:center;">
            <h2 style="margin-bottom:0;">{nome_loja}</h2>
            <div style="color:#666;">{telefone_loja}</div>
        </div>
        <hr>
        <table width="100%" cellspacing="4">
            <tr><td><b>Cliente:</b></td><td>{self.cliente.get('nome', '')}</td></tr>
            <tr><td><b>CPF/CNPJ:</b></td><td>{self.cliente.get('cpf_cnpj') or '—'}</td></tr>
            <tr><td><b>Telefone:</b></td><td>{self.cliente.get('telefone') or '—'}</td></tr>
            <tr><td><b>Emitido em:</b></td><td>{agora}</td></tr>
        </table>
        <h3>Extrato Financeiro</h3>
        <table width="100%" border="1" cellspacing="0" cellpadding="6">
            <tr style="background:#f0f0f0;">
                <th>Data</th><th>Descrição</th><th>Débito</th>
                <th>Crédito</th><th>Saldo</th>
            </tr>
            {linhas_html}
        </table>
        {bloco_observacoes}
        <hr>
        <table width="100%">
            <tr>
                <td><b>Total Devedor:</b></td>
                <td align="right"><b>{_formatar_moeda(saldo)}</b></td>
            </tr>
            <tr>
                <td>Responsável:</td>
                <td align="right">{responsavel}</td>
            </tr>
        </table>
        """

    def _montar_documento_extrato(self):

        documento = QTextDocument()
        documento.setDefaultFont(QFont(tokens.FONTE_FAMILIA_PADRAO, 10))
        documento.setHtml(self._montar_html_extrato())

        return documento

    def imprimir_extrato(self):

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
