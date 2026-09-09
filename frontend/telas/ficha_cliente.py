import csv
from datetime import date, datetime
from urllib.parse import quote

from PySide6.QtCore import Qt, QDate, QUrl
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
from services import impressora_termica_service, preferencias_service

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
        tamanho_fixo_seguro(self, 420, 460)
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
                    f"{formatar_moeda(saldo_projetado)}, acima do limite "
                    f"de crédito cadastrado ({formatar_moeda(limite)}).\n\n"
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
        tamanho_fixo_seguro(self, 420, 560)
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
            f"{formatar_moeda(saldo_devedor)}"
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

        bt_confirmar = BotaoPrimario("Salvar")
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
            QMessageBox.warning(self, "Atenção", "Informe um valor válido.")
            return

        if valor <= 0:
            QMessageBox.warning(
                self, "Atenção", "Informe um valor maior que zero."
            )
            return

        response = lancar_haver(
            self.cliente["id"],
            valor,
            self.descricao.text().strip() or "Haver",
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

    _TIMELINE_PAGINA = 30  # scroll incremental: 30 lançamentos por vez

    def __init__(self, cliente, parent=None):

        super().__init__(parent)

        self.cliente = cliente
        self._vendas_por_id = {}
        self._nomes_produto = {}
        self._movimentos = []

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

        linha_nome.addWidget(self.lbl_titulo)
        linha_nome.addWidget(self.badge_ativo, 0)
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

        layout.addLayout(linha_contato)

        self._atualizar_cabecalho(self.cliente)
        self._atualizar_avatar(self.cliente)

        return cabecalho

    def _construir_menu_whatsapp(self):
        """O botão WhatsApp do cabeçalho virou um menu com as ações
        mais usadas -- antes eram vários botões espalhados (inclusive
        "Enviar Último Comprovante", que morava na barra de ações)."""

        menu = QMenu(self)

        menu.addAction("Enviar Extrato Completo", self.enviar_extrato_whatsapp)
        menu.addAction("Enviar Último Comprovante", self.enviar_ultimo_comprovante)
        menu.addAction("Enviar Cobrança", self.enviar_cobranca_whatsapp)
        menu.addAction("Enviar Saldo Devedor", self.enviar_saldo_devedor_whatsapp)
        menu.addAction("Enviar Haver", self.enviar_haver_whatsapp)
        menu.addAction("Enviar Cadastro do Cliente", self.enviar_cadastro_whatsapp)

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
        self.lbl_saldo_valor = self._mini_card(linha1, "SALDO ATUAL")
        self.lbl_total_comprado = self._mini_card(linha1, "TOTAL COMPRADO")
        self.lbl_total_pago_card = self._mini_card(linha1, "TOTAL PAGO")
        self.lbl_ultima_compra = self._mini_card(linha1, "ÚLTIMA COMPRA")
        self.lbl_ultimo_pagamento = self._mini_card(linha1, "ÚLTIMO PAGAMENTO")

        # linha 2 -- perfil/relacionamento do cliente
        self.lbl_cliente_desde = self._mini_card(linha2, "CLIENTE DESDE")
        self.lbl_status_financeiro = self._mini_card(linha2, "STATUS FINANCEIRO")
        self.lbl_score = self._mini_card(linha2, "PONTUAÇÃO")
        self.lbl_dias_desde_ultima_compra = self._mini_card(linha2, "DIAS SEM COMPRAR")
        self.lbl_limite_credito = self._mini_card(linha2, "LIMITE DE CRÉDITO")

        layout_externo.addLayout(linha1)
        layout_externo.addLayout(linha2)

        self.lbl_aviso_status = QLabel("")
        self.lbl_aviso_status.setAlignment(Qt.AlignCenter)
        self.lbl_aviso_status.setWordWrap(True)
        layout_externo.addWidget(self.lbl_aviso_status)

        return container

    def _mini_card(self, layout, titulo):

        card = QFrame()
        card.setFixedSize(self._LARGURA_MINI_CARD, self._ALTURA_MINI_CARD)
        card.setStyleSheet(f"""
            background:{tokens.CARD}; border:1px solid {tokens.BORDA};
            border-radius:{tokens.RADIUS_SM}px;
        """)

        col = QVBoxLayout(card)
        col.setContentsMargins(10, 6, 10, 6)
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
            f" ({data}, {formatar_moeda(ultima_venda['valor_total'])})?",
        )

        if resposta != QMessageBox.Yes:
            return

        comprovante_acoes.enviar_whatsapp(ultima_venda["id"], self)

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

    def _cabecalho_texto_whatsapp(self, titulo):

        config = api.configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"

        return f"🛍️ {nome_loja}\n*{titulo}*"

    def enviar_extrato_whatsapp(self):
        """'Extrato Completo' -- envia automaticamente pelo WhatsApp o
        texto com todas as movimentações do cliente (ver seção 8 do
        pedido de redesenho da ficha)."""

        saldo = saldo_cliente(self.cliente["id"])

        agr = cliente_analise.calcular_agregados(
            self.cliente, [mov for mov, _ in reversed(self._movimentos)]
        )

        cliente_desde = (
            agr["criado_em"].strftime("%d/%m/%Y") if agr["criado_em"] else "—"
        )
        status = cliente_analise.status_financeiro(agr)

        total_pago = sum(
            float(mov.get("valor", 0) or 0)
            for mov, _ in self._movimentos
            if mov.get("tipo") == "PAGAMENTO"
        )

        linhas = []

        for mov, saldo_apos in reversed(self._movimentos):

            data = str(mov.get("data", ""))
            if "T" in data:
                data = data.replace("T", " ")[:16]

            tipo = mov.get("tipo", "")
            rotulo = {
                "COMPRA": "🛒 Compra",
                "PAGAMENTO": "💵 Pagamento",
                "HAVER": "💰 Haver",
            }.get(tipo, tipo)

            valor = float(mov.get("valor", 0) or 0)
            sinal = "+" if tipo == "COMPRA" else "-"

            linhas.append(
                f"{data} | {rotulo} | {self._descricao_com_itens(mov)} | "
                f"{sinal} {formatar_moeda(valor)} | "
                f"Saldo: {formatar_moeda(saldo_apos)}"
            )

        movimentacoes = "\n".join(linhas) if linhas else "Nenhuma movimentação registrada."

        texto = (
            f"{self._cabecalho_texto_whatsapp('EXTRATO DO CLIENTE')}\n\n"
            f"Cliente: {self.cliente.get('nome', '')}\n"
            f"Telefone: {self.cliente.get('telefone') or '—'}\n"
            f"Status: {status}\n"
            f"Cliente desde: {cliente_desde}\n"
            f"Saldo Atual: {formatar_moeda(saldo)}\n\n"
            f"*MOVIMENTAÇÕES*\n"
            f"{movimentacoes}\n\n"
            f"Total Comprado: {formatar_moeda(agr['total_comprado'])}\n"
            f"Total Pago: {formatar_moeda(total_pago)}\n"
            f"Saldo Devedor: {formatar_moeda(saldo)}\n\n"
            f"Muito obrigado pela preferência!"
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

        texto = (
            f"{self._cabecalho_texto_whatsapp('COBRANÇA')}\n\n"
            f"Olá, {self.cliente.get('nome', '')}! 👋\n\n"
            f"Passando pra lembrar que você tem um saldo em aberto no "
            f"valor de {formatar_moeda(saldo)}.\n\n"
            f"Qualquer dúvida, é só chamar. Obrigado!"
        )

        self._enviar_texto_whatsapp(texto, "Enviar Cobrança")

    def enviar_saldo_devedor_whatsapp(self):
        """Informativo -- ao contrário da cobrança, não trava se o
        saldo for zero (o cliente pode querer confirmar que está em
        dia)."""

        saldo = saldo_cliente(self.cliente["id"])

        texto = (
            f"{self._cabecalho_texto_whatsapp('SALDO DEVEDOR')}\n\n"
            f"Olá, {self.cliente.get('nome', '')}!\n"
            f"Seu saldo devedor atual é de {formatar_moeda(saldo)}."
        )

        self._enviar_texto_whatsapp(texto, "Enviar Saldo Devedor")

    def enviar_haver_whatsapp(self):
        """Avisa sobre o crédito (Haver) mais recente lançado a favor
        do cliente."""

        haveres = [
            (mov, saldo_apos)
            for mov, saldo_apos in self._movimentos
            if mov.get("tipo") == "HAVER"
        ]

        if not haveres:
            QMessageBox.information(
                self,
                "Haver",
                "Este cliente ainda não tem nenhum crédito (Haver) lançado.",
            )
            return

        mov, saldo_apos = haveres[0]  # self._movimentos já é mais-novo primeiro

        data = str(mov.get("data", ""))
        if "T" in data:
            data = data.replace("T", " ")[:16]

        texto = (
            f"{self._cabecalho_texto_whatsapp('CRÉDITO (HAVER)')}\n\n"
            f"Olá, {self.cliente.get('nome', '')}!\n"
            f"Você recebeu um crédito de "
            f"{formatar_moeda(float(mov.get('valor', 0) or 0))} em {data}.\n"
            f"Motivo: {mov.get('descricao') or '—'}\n\n"
            f"Seu saldo devedor atualizado é de {formatar_moeda(saldo_apos)}."
        )

        self._enviar_texto_whatsapp(texto, "Enviar Haver")

    def enviar_cadastro_whatsapp(self):
        """Ficha completa do cliente via WhatsApp."""

        cliente = self.cliente
        saldo = saldo_cliente(cliente["id"])

        agr = cliente_analise.calcular_agregados(
            cliente, [mov for mov, _ in reversed(self._movimentos)]
        )
        cliente_desde = (
            agr["criado_em"].strftime("%d/%m/%Y") if agr["criado_em"] else "—"
        )

        partes = [self._cabecalho_texto_whatsapp("CADASTRO DO CLIENTE"), ""]
        partes.append(f"Nome: {cliente.get('nome', '')}")

        if cliente.get("cpf_cnpj"):
            partes.append(f"CPF/CNPJ: {cliente['cpf_cnpj']}")
        if cliente.get("telefone"):
            partes.append(f"Telefone: {cliente['telefone']}")
        if cliente.get("email"):
            partes.append(f"E-mail: {cliente['email']}")

        endereco = ", ".join(
            filter(None, [cliente.get("endereco"), cliente.get("cidade"), cliente.get("estado")])
        )
        if endereco:
            partes.append(f"Endereço: {endereco}")

        if cliente.get("data_nascimento"):
            partes.append(f"Data de Nascimento: {cliente['data_nascimento']}")

        partes.append(f"Cliente desde: {cliente_desde}")
        partes.append(f"Saldo Atual: {formatar_moeda(saldo)}")
        partes.append("")
        partes.append("Muito obrigado pela preferência!")

        self._enviar_texto_whatsapp("\n".join(partes), "Enviar Cadastro do Cliente")

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

        bt_adicionar = BotaoPrimario("Adicionar")
        bt_adicionar.setFixedHeight(36)
        bt_adicionar.setAutoDefault(False)
        bt_adicionar.clicked.connect(self.adicionar_observacao)

        linha_nova.addWidget(self.campo_nova_observacao)
        linha_nova.addWidget(bt_adicionar)

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
            ("TODOS", "Todos"),
            ("COMPRA", "🛒 Compras"),
            ("PAGAMENTO", "💵 Pagamentos"),
            ("HAVER", "💰 Haver"),
            ("AJUSTES", "Ajustes"),
            ("30DIAS", "Últimos 30 dias"),
        ]

        for chave, texto in opcoes:

            botao = QPushButton(texto)
            botao.setCheckable(True)
            botao.setChecked(chave == "TODOS")
            botao.setCursor(Qt.PointingHandCursor)
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
                lambda _, chave=chave: self._selecionar_filtro_timeline(chave)
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

    def _selecionar_filtro_timeline(self, chave):

        self._filtro_timeline = chave

        for k, botao in self.botoes_filtro_timeline.items():
            botao.setChecked(k == chave)

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

        if len(historico) > len(visiveis):
            lbl_mais = QLabel(
                f"Mostrando {len(visiveis)} de {len(historico)} — "
                "role pra ver mais"
            )
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
            rotulo_tipo = "🔄 Ajuste"
        elif tipo == "HAVER":
            cor = tokens.ALERTA
            icone_nome = "gift"
            rotulo_tipo = "💰 Haver"
        elif tipo == "COMPRA":
            cor = tokens.PRIMARIA
            icone_nome = "shopping-cart"
            rotulo_tipo = "🛒 Compra"
        else:
            cor = tokens.SECUNDARIA
            icone_nome = "check"
            rotulo_tipo = "💵 Pagamento"

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
        lbl_tipo.setStyleSheet(f"""
            background:transparent; border:none; color:{cor};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800;
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

        self.lbl_saldo_valor.setText(formatar_moeda(saldo))
        self.lbl_saldo_valor.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_SM}px;
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
        self.lbl_score.setText(cliente_analise.calcular_pontuacao(agr))

        limite_credito = self.cliente.get("limite_credito")
        self.lbl_limite_credito.setText(
            formatar_moeda(limite_credito) if limite_credito else "Sem limite"
        )

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

        # painel lateral
        self.lbl_resumo_total_comprado.setText(formatar_moeda(total_comprado))
        self.lbl_resumo_total_pago.setText(formatar_moeda(total_pago))
        self.lbl_resumo_saldo_atual.setText(formatar_moeda(saldo_atual))
        self.lbl_resumo_maior_compra.setText(formatar_moeda(maior_compra))
        self.lbl_resumo_ultima_compra.setText(_data_curta(agr["ultima_compra"]))
        self.lbl_resumo_ticket_medio.setText(formatar_moeda(ticket_medio))
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

    def lancar_haver(self):

        saldo = saldo_cliente(self.cliente["id"])

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

            debito = formatar_moeda(valor) if tipo == "COMPRA" else ""
            credito = formatar_moeda(valor) if tipo == "PAGAMENTO" else ""

            linhas_tabela.append(
                f"<tr>"
                f"<td>{data}</td>"
                f"<td>{descricao}</td>"
                f"<td align='right'>{debito}</td>"
                f"<td align='right'>{credito}</td>"
                f"<td align='right'>{formatar_moeda(saldo_apos)}</td>"
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
                <td align="right"><b>{formatar_moeda(saldo)}</b></td>
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
