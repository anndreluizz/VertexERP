import os
import tempfile
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QLabel,
    QPushButton,
    QComboBox,
    QScrollArea,
    QMenu,
    QMessageBox,
)

from services.categoria_despesa_service import listar_categorias_despesa
from services.loja_service import listar_lojas
from services.conta_pagar_service import (
    listar_contas_pagar,
    excluir_conta_pagar,
    obter_documento_conta_pagar,
    obter_comprovante_pagamento_conta_pagar,
)
from services import api
from services.worker import rodar_em_thread
from telas.cadastro_despesa import CadastroDespesaDialog
from telas.pagamento_despesa import PagamentoDespesaDialog

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import BotaoPrimario, BotaoSecundario, CampoTexto, Card, CardKPI
from utils.formatacao import formatar_moeda


def _status_real(conta):
    """PENDENTE com vencimento no passado vira VENCIDA na visualizacao
    — o backend nunca grava esse status, e essa e a unica derivacao
    que importa mostrar pro usuario (nao faz sentido gravar VENCIDA
    persistido, ja que o mesmo registro fica cada vez mais vencido
    conforme o tempo passa sem nenhuma acao)."""

    status = conta.get("status", "PENDENTE")

    if status != "PENDENTE":
        return status

    try:
        vencimento = datetime.fromisoformat(
            conta["data_vencimento"]
        ).date()
    except (ValueError, TypeError, KeyError):
        return status

    if vencimento < date.today():
        return "VENCIDA"

    return status


def _vencimento(conta):
    try:
        return datetime.fromisoformat(conta["data_vencimento"]).date()
    except (ValueError, TypeError, KeyError):
        return None


def _texto_vencimento(conta, status):
    """Vencimento em linguagem de gente ("Venceu há 3 dias", "Vence
    amanhã", "Em 5 dias") + a data -- e a cor que ele deve ter."""

    venc = _vencimento(conta)
    if venc is None:
        return conta.get("data_vencimento", ""), tokens.TEXTO_SECUNDARIO

    data = venc.strftime("%d/%m/%Y")
    dias = (venc - date.today()).days

    if status == "PAGO":
        try:
            pago_em = datetime.fromisoformat(conta["data_pagamento"]).strftime("%d/%m/%Y")
            return f"Paga em {pago_em} · vencimento {data}", tokens.TEXTO_SECUNDARIO
        except (ValueError, TypeError, KeyError):
            return f"Paga · vencimento {data}", tokens.TEXTO_SECUNDARIO
    if status == "CANCELADO":
        return f"Cancelada · vencimento {data}", tokens.TEXTO_TERCIARIO
    if dias < 0:
        n = -dias
        return f"Venceu há {n} dia{'s' if n != 1 else ''} · {data}", tokens.ERRO
    if dias == 0:
        return f"Vence hoje · {data}", tokens.ERRO
    if dias == 1:
        return f"Vence amanhã · {data}", tokens.ALERTA_TEXTO
    return f"Em {dias} dias · {data}", tokens.TEXTO_SECUNDARIO


def _grupo_da_conta(conta):
    """Em qual bloco da lista a conta entra (ordem de urgência)."""

    status = _status_real(conta)
    if status == "PAGO":
        return "PAGAS"
    if status == "CANCELADO":
        return "CANCELADAS"
    if status == "VENCIDA":
        return "VENCIDAS"
    venc = _vencimento(conta)
    if venc is None:
        return "DEPOIS"
    dias = (venc - date.today()).days
    if dias == 0:
        return "HOJE"
    if dias <= 7:
        return "SEMANA"
    return "DEPOIS"


# (chave, título, cor do título) -- ordem de exibição
_GRUPOS = [
    ("VENCIDAS", "Vencidas", "ERRO"),
    ("HOJE", "Vencem hoje", "ERRO"),
    ("SEMANA", "Próximos 7 dias", "ALERTA_TEXTO"),
    ("DEPOIS", "Mais adiante", "TEXTO"),
    ("PAGAS", "Pagas", "SECUNDARIA"),
    ("CANCELADAS", "Canceladas", "TEXTO_TERCIARIO"),
]


class DespesaLinha(QFrame):
    """Uma conta numa linha: faixa colorida de situação, descrição e
    categoria, vencimento em texto ("Vence amanhã"), valor e o botão
    Pagar à mão. Mesmos sinais/menu do antigo DespesaCard."""

    editar_solicitado = Signal(dict)
    excluir_solicitado = Signal(dict)
    pagar_solicitado = Signal(dict)
    duplicar_solicitado = Signal(dict)
    ver_documento_solicitado = Signal(dict)
    ver_comprovante_solicitado = Signal(dict)

    COR_STATUS = {
        "PAGO": "SECUNDARIA",
        "PENDENTE": "ALERTA",
        "VENCIDA": "ERRO",
        "CANCELADO": "BORDA_FORTE",
    }

    def __init__(self, conta):

        super().__init__()

        self.conta = conta
        status = _status_real(conta)
        cor_faixa = getattr(tokens, self.COR_STATUS.get(status, "BORDA"))

        self.setObjectName("DespesaLinha")
        self.setStyleSheet(f"""
            #DespesaLinha {{
                background:transparent;
                border:none;
                border-left:4px solid {cor_faixa};
                border-bottom:1px solid {tokens.BORDA};
            }}
            #DespesaLinha:hover {{ background:{tokens.FUNDO}; }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        col = QVBoxLayout()
        col.setSpacing(2)

        linha_titulo = QHBoxLayout()
        linha_titulo.setSpacing(6)
        descricao = QLabel(conta.get("descricao") or "Despesa")
        apagada = status in ("PAGO", "CANCELADO")
        descricao.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tokens.TAMANHO_MD}px; font-weight:700;
            color:{tokens.TEXTO_SECUNDARIO if apagada else tokens.TEXTO};
        """)
        linha_titulo.addWidget(descricao)
        if conta.get("tem_documento"):
            clipe = QLabel()
            clipe.setToolTip("Tem documento anexado (boleto/nota)")
            clipe.setStyleSheet("background:transparent; border:none;")
            clipe.setPixmap(icone_pixmap("file-text", cor=tokens.TEXTO_TERCIARIO, tamanho=13))
            linha_titulo.addWidget(clipe)
        linha_titulo.addStretch()
        col.addLayout(linha_titulo)

        texto_venc, cor_venc = _texto_vencimento(conta, status)
        urgente = cor_venc in (tokens.ERRO, tokens.ALERTA_TEXTO)

        linha_detalhe = QHBoxLayout()
        linha_detalhe.setSpacing(0)
        if conta.get("categoria"):
            lbl_cat = QLabel(f"{conta['categoria']}  ·  ")
            lbl_cat.setStyleSheet(f"""
                background:transparent; border:none;
                font-size:{tokens.TAMANHO_SM}px; color:{tokens.TEXTO_TERCIARIO};
            """)
            linha_detalhe.addWidget(lbl_cat)
        lbl_venc = QLabel(texto_venc)
        lbl_venc.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tokens.TAMANHO_SM}px; color:{cor_venc};
            font-weight:{700 if urgente else 400};
        """)
        linha_detalhe.addWidget(lbl_venc)
        linha_detalhe.addStretch()
        col.addLayout(linha_detalhe)

        layout.addLayout(col, stretch=1)

        valor = QLabel(formatar_moeda(conta.get("valor", 0)))
        valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        valor.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tokens.TAMANHO_MD}px; font-weight:800;
            color:{tokens.TEXTO_SECUNDARIO if apagada else tokens.TEXTO};
        """)
        layout.addWidget(valor)

        # espaço fixo pro botão Pagar, mesmo quando não tem: mantém os
        # valores alinhados na mesma coluna em todas as linhas
        area_pagar = QWidget()
        area_pagar.setFixedWidth(96)
        area_pagar.setStyleSheet("background:transparent;")
        lay_pagar = QHBoxLayout(area_pagar)
        lay_pagar.setContentsMargins(0, 0, 0, 0)
        if status in ("PENDENTE", "VENCIDA"):
            bt_pagar = BotaoSecundario("Pagar", icone_nome="check")
            bt_pagar.setMinimumHeight(34)
            bt_pagar.clicked.connect(lambda: self.pagar_solicitado.emit(self.conta))
            lay_pagar.addWidget(bt_pagar)
        layout.addWidget(area_pagar)

        bt_menu = QPushButton()
        bt_menu.setFixedSize(30, 30)
        bt_menu.setCursor(Qt.PointingHandCursor)
        bt_menu.setIcon(icone("more-vertical", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        bt_menu.setToolTip("Mais opções")
        bt_menu.setAccessibleName("Mais opções")
        bt_menu.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.BORDA}; }}
            QPushButton::menu-indicator {{ image:none; width:0; }}
        """)
        bt_menu.setMenu(self._construir_menu())
        layout.addWidget(bt_menu)

    def mouseDoubleClickEvent(self, event):
        self.editar_solicitado.emit(self.conta)
        super().mouseDoubleClickEvent(event)

    def _construir_menu(self):

        menu = QMenu(self)

        if self.conta.get("tem_documento"):
            menu.addAction(
                "Ver documento",
                lambda: self.ver_documento_solicitado.emit(self.conta),
            )

        if self.conta.get("tem_comprovante_pagamento"):
            menu.addAction(
                "Ver comprovante de pagamento",
                lambda: self.ver_comprovante_solicitado.emit(self.conta),
            )

        menu.addAction(
            "Editar", lambda: self.editar_solicitado.emit(self.conta)
        )
        menu.addAction(
            "Duplicar", lambda: self.duplicar_solicitado.emit(self.conta)
        )
        # backend exige contas_pagar.excluir -- sem ela nem mostra
        if api.usuario_tem_permissao("contas_pagar.excluir"):
            menu.addSeparator()
            menu.addAction(
                "Excluir", lambda: self.excluir_solicitado.emit(self.conta)
            )

        return menu


class ContasPagar(QWidget):

    voltar = Signal()

    # (chave do filtro, rótulo) -- PAGA era comparada com o status
    # "PAGO" do backend e nunca batia; agora a chave é o próprio status
    FILTROS_STATUS = [
        ("TODAS", "Todas"),
        ("VENCIDA", "Vencidas"),
        ("PENDENTE", "A vencer"),
        ("PAGO", "Pagas"),
    ]
    FILTROS_PERIODO = [
        ("TODOS", "Qualquer data"),
        ("HOJE", "Vence hoje"),
        ("SEMANA", "Próximos 7 dias"),
        ("MES", "Este mês"),
        ("ANO", "Este ano"),
    ]

    def __init__(self):
        super().__init__()

        self.contas = []
        self.filtro_status = "TODAS"
        self.filtro_periodo = "TODOS"
        self._carregando = False

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(12)

        self.bt_voltar = QPushButton()
        self.bt_voltar.setFixedSize(36, 36)
        self.bt_voltar.setCursor(Qt.PointingHandCursor)
        self.bt_voltar.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        self.bt_voltar.setToolTip("Voltar")
        self.bt_voltar.setAccessibleName("Voltar")
        self.bt_voltar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        icone_titulo = QLabel()
        icone_titulo.setFixedSize(36, 36)
        icone_titulo.setAlignment(Qt.AlignCenter)
        icone_titulo.setStyleSheet(f"""
            background:{tokens.ALERTA_CLARO}; border-radius:{tokens.RADIUS_SM}px;
        """)
        icone_titulo.setPixmap(icone_pixmap("wallet", cor=tokens.ALERTA, tamanho=18))

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Contas a Pagar")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            "Acompanhe despesas, vencimentos e pagamentos do estabelecimento."
        )
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addWidget(icone_titulo)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()

        self.bt_nova_despesa = BotaoPrimario("Nova despesa", icone_nome="plus")
        self.bt_nova_despesa.clicked.connect(self.nova_despesa)

        cabecalho.addWidget(self.bt_nova_despesa)

        layout.addLayout(cabecalho)

        # ======================
        # KPIS
        # ======================

        kpis_layout = QGridLayout()
        kpis_layout.setSpacing(14)

        # 4 números (eram 7 em duas linhas, incluindo um "valor médio"
        # que não ajuda a decidir nada). Ficam fixos no topo.
        self.card_aberto = CardKPI("A pagar", "wallet", tokens.PRIMARIA, destaque=True)
        self.card_vencidas = CardKPI("Vencidas", "alert-triangle", tokens.ERRO)
        self.card_proximos_7 = CardKPI("Próximos 7 dias", "calendar", tokens.ALERTA)
        self.card_pago = CardKPI("Pago no mês", "check", tokens.SECUNDARIA)

        for coluna, card in enumerate((
            self.card_aberto, self.card_vencidas, self.card_proximos_7, self.card_pago,
        )):
            kpis_layout.addWidget(card, 0, coluna)
            kpis_layout.setColumnStretch(coluna, 1)

        layout.addLayout(kpis_layout)

        # ======================
        # FILTROS
        # ======================

        estilo_combo = f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:0 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """

        linha_busca = QHBoxLayout()
        linha_busca.setSpacing(10)

        self.pesquisa = CampoTexto("Buscar por descrição ou categoria...")
        self.pesquisa.setMinimumWidth(240)
        self.pesquisa.textChanged.connect(self._renderizar_lista)
        linha_busca.addWidget(self.pesquisa, stretch=1)

        self.combo_categoria = QComboBox()
        self.combo_categoria.setMinimumHeight(40)
        self.combo_categoria.setMinimumWidth(180)
        self.combo_categoria.setCursor(Qt.PointingHandCursor)
        self.combo_categoria.setStyleSheet(estilo_combo)
        self.combo_categoria.currentTextChanged.connect(self._renderizar_lista)
        linha_busca.addWidget(self.combo_categoria)

        # período em lista (eram 5 botões numa segunda fileira)
        self.combo_periodo = QComboBox()
        for chave, rotulo in self.FILTROS_PERIODO:
            self.combo_periodo.addItem(rotulo, chave)
        self.combo_periodo.setMinimumHeight(40)
        self.combo_periodo.setCursor(Qt.PointingHandCursor)
        self.combo_periodo.setStyleSheet(estilo_combo)
        self.combo_periodo.currentIndexChanged.connect(
            lambda _i: self._filtrar_periodo(self.combo_periodo.currentData())
        )
        linha_busca.addWidget(self.combo_periodo)

        self.combo_loja_filtro = QComboBox()
        self.combo_loja_filtro.setMinimumHeight(40)
        self.combo_loja_filtro.setCursor(Qt.PointingHandCursor)
        self.combo_loja_filtro.setStyleSheet(estilo_combo)
        self._carregar_combo_lojas()
        self.combo_loja_filtro.currentIndexChanged.connect(self.carregar)
        linha_busca.addWidget(self.combo_loja_filtro)

        layout.addLayout(linha_busca)

        linha_filtros = QHBoxLayout()
        linha_filtros.setSpacing(8)

        self.botoes_status = {}

        for filtro, rotulo in self.FILTROS_STATUS:

            botao = QPushButton(rotulo)
            botao.setProperty("rotulo", rotulo)
            botao.setCheckable(True)
            botao.setCursor(Qt.PointingHandCursor)
            botao.setMinimumHeight(36)
            botao.clicked.connect(
                lambda _checked, f=filtro: self._filtrar_status(f)
            )

            self.botoes_status[filtro] = botao
            linha_filtros.addWidget(botao)

        linha_filtros.addStretch()

        self.lbl_contagem = QLabel("")
        self.lbl_contagem.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        linha_filtros.addWidget(self.lbl_contagem)

        layout.addLayout(linha_filtros)

        self._estilizar_pills(self.botoes_status, self.filtro_status)

        # ======================
        # KPIS + LISTA (rolam juntos)
        # ======================

        self.area_rolagem = QScrollArea()
        self.area_rolagem.setWidgetResizable(True)
        self.area_rolagem.setStyleSheet(
            "QScrollArea { border:none; background:transparent; }"
        )

        conteudo_rolavel = QWidget()
        conteudo_rolavel.setStyleSheet("background:transparent;")

        self.lista_layout = QVBoxLayout(conteudo_rolavel)
        self.lista_layout.setContentsMargins(0, 0, 0, 0)
        self.lista_layout.setSpacing(0)
        self.lista_layout.setAlignment(Qt.AlignTop)

        self.area_rolagem.setWidget(conteudo_rolavel)

        cartao_lista = Card()
        lay_cartao = QVBoxLayout(cartao_lista)
        lay_cartao.setContentsMargins(0, 4, 0, 4)
        lay_cartao.addWidget(self.area_rolagem)

        layout.addWidget(cartao_lista, stretch=1)

        # Recorte simples de "tempo real": sem servidor empurrando
        # nada, so recarrega sozinho enquanto a tela estiver visivel
        # -- suficiente pra um pagamento feito no celular aparecer
        # aqui sem precisar sair e voltar da tela.
        self._timer_auto_atualizacao = QTimer(self)
        self._timer_auto_atualizacao.setInterval(20_000)
        self._timer_auto_atualizacao.timeout.connect(self.carregar)

    def showEvent(self, event):
        super().showEvent(event)
        # achado nesta conversao: nada em __init__ chamava carregar()
        # -- a tela nascia vazia e so' mostrava dado depois do 1o tick
        # de 20s deste timer (ou de alguem trocar o filtro de loja).
        # Carrega na hora de ficar visivel, e so' DEPOIS liga o timer
        # de auto-atualizacao.
        self.carregar()
        self._timer_auto_atualizacao.start()

    def hideEvent(self, event):
        self._timer_auto_atualizacao.stop()
        super().hideEvent(event)

    def _estilizar_pills(self, botoes, ativo):

        for chave, botao in botoes.items():

            selecionado = chave == ativo

            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.PRIMARIA_CLARA if selecionado else tokens.CARD};
                    color: {tokens.PRIMARIA if selecionado else tokens.TEXTO_SECUNDARIO};
                    border: 1px solid {tokens.PRIMARIA_CLARA if selecionado else tokens.BORDA};
                    border-radius: 18px;
                    padding: 0 16px; font-size: {tokens.TAMANHO_SM}px;
                    font-weight: {700 if selecionado else 600};
                }}
                QPushButton:hover {{
                    background: {tokens.PRIMARIA_CLARA if selecionado else tokens.FUNDO};
                }}
            """)

    # ==========================================
    # CARREGAMENTO
    # ==========================================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True

        loja_id = self.combo_loja_filtro.currentData()

        rodar_em_thread(
            self,
            listar_contas_pagar,
            loja_id,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _ao_carregar_sucesso(self, contas):
        try:
            self.contas = contas
            self._carregar_categorias()
            self._atualizar_kpis()
            self._renderizar_lista()
        except Exception as erro:
            self._ao_carregar_erro(erro)

    def _ao_carregar_erro(self, erro):
        # nao interrompe com QMessageBox aqui de proposito -- o timer
        # de 20s roda em segundo plano sem o usuario ter pedido nada,
        # um popup de erro a cada tentativa falha seria intrusivo
        # demais; so' loga pra nao falhar silencioso de verdade
        print(f"[contas_pagar] falha ao atualizar: {erro}")

    def _ao_carregar_finalizado(self):
        self._carregando = False

    def _carregar_combo_lojas(self):

        self.combo_loja_filtro.blockSignals(True)
        self.combo_loja_filtro.clear()
        self.combo_loja_filtro.addItem("Todas as lojas", None)
        self.combo_loja_filtro.blockSignals(False)

        rodar_em_thread(
            self,
            listar_lojas,
            ao_sucesso=self._ao_carregar_combo_lojas_sucesso,
        )

    def _ao_carregar_combo_lojas_sucesso(self, lojas):

        self.combo_loja_filtro.blockSignals(True)

        for loja in lojas:
            self.combo_loja_filtro.addItem(loja["nome"], loja["id"])

        self.combo_loja_filtro.blockSignals(False)

    def _carregar_categorias(self):

        selecionada = self.combo_categoria.currentText()

        self.combo_categoria.blockSignals(True)
        self.combo_categoria.clear()
        self.combo_categoria.addItem("Todas as categorias")

        nomes = sorted({
            c.get("categoria") for c in self.contas if c.get("categoria")
        })
        self.combo_categoria.addItems(nomes)

        if selecionada and self.combo_categoria.findText(selecionada) >= 0:
            self.combo_categoria.setCurrentText(selecionada)

        self.combo_categoria.blockSignals(False)

    def _atualizar_kpis(self):

        contas_validas = [
            c for c in self.contas
            if c.get("status") != "CANCELADO"
        ]

        hoje = date.today()

        total_pago = sum(
            float(c.get("valor", 0)) for c in contas_validas
            if c.get("status") == "PAGO"
        )

        em_aberto = sum(
            float(c.get("valor", 0)) for c in contas_validas
            if _status_real(c) == "PENDENTE"
        )

        vencidas_lista = [
            c for c in contas_validas
            if _status_real(c) == "VENCIDA"
        ]
        vencidas_total = sum(float(c.get("valor", 0)) for c in vencidas_lista)

        vence_hoje_total = sum(
            float(c.get("valor", 0)) for c in contas_validas
            if _status_real(c) == "PENDENTE" and _vencimento(c) == hoje
        )

        limite_7 = hoje + timedelta(days=7)
        proximos_7_total = sum(
            float(c.get("valor", 0)) for c in contas_validas
            if _status_real(c) == "PENDENTE"
            and _vencimento(c) is not None
            and hoje < _vencimento(c) <= limite_7
        )

        inicio_mes = hoje.replace(day=1)
        def _data_pagamento(c):
            try:
                return datetime.fromisoformat(c["data_pagamento"]).date()
            except (ValueError, TypeError, KeyError):
                return None

        # pelo dia em que foi PAGA (não pelo vencimento): conta de
        # setembro paga hoje entra no "pago no mês" de outubro
        pago_mes = sum(
            float(c.get("valor", 0)) for c in contas_validas
            if c.get("status") == "PAGO"
            and (_data_pagamento(c) or _vencimento(c) or hoje) >= inicio_mes
        )

        pendentes = [c for c in contas_validas if _status_real(c) == "PENDENTE"]
        a_pagar = em_aberto + vencidas_total
        qtd_7 = sum(
            1 for c in pendentes
            if _vencimento(c) is not None and hoje <= _vencimento(c) <= limite_7
        )

        self.card_aberto.definir_valor(formatar_moeda(a_pagar))
        self.card_aberto.definir_legenda(
            f"{len(pendentes) + len(vencidas_lista)} contas em aberto"
        )
        self.card_vencidas.definir_valor(formatar_moeda(vencidas_total))
        self.card_vencidas.definir_legenda(
            f"{len(vencidas_lista)} conta{'s' if len(vencidas_lista) != 1 else ''} atrasada{'s' if len(vencidas_lista) != 1 else ''}"
            if vencidas_lista else "nenhuma atrasada"
        )
        self.card_proximos_7.definir_valor(
            formatar_moeda(proximos_7_total + vence_hoje_total)
        )
        self.card_proximos_7.definir_legenda(
            f"{qtd_7} conta{'s' if qtd_7 != 1 else ''}"
            + (f" · {formatar_moeda(vence_hoje_total)} vence hoje" if vence_hoje_total else "")
        )
        self.card_pago.definir_valor(formatar_moeda(pago_mes))
        self.card_pago.definir_legenda(f"total pago: {formatar_moeda(total_pago)}")

        contagem = {
            "TODAS": len(contas_validas),
            "VENCIDA": len(vencidas_lista),
            "PENDENTE": len(pendentes),
            "PAGO": sum(1 for c in contas_validas if c.get("status") == "PAGO"),
        }
        for chave, botao in self.botoes_status.items():
            botao.setText(f"{botao.property('rotulo')}  {contagem.get(chave, 0)}")

    def _filtrar_status(self, filtro):

        self.filtro_status = filtro
        self._estilizar_pills(self.botoes_status, filtro)
        self._renderizar_lista()

    def _filtrar_periodo(self, filtro):

        self.filtro_periodo = filtro
        self._renderizar_lista()

    def _dentro_do_periodo(self, conta):

        if self.filtro_periodo == "TODOS":
            return True

        venc = _vencimento(conta)

        if venc is None:
            return False

        hoje = date.today()

        if self.filtro_periodo == "HOJE":
            return venc == hoje

        if self.filtro_periodo == "SEMANA":
            return hoje <= venc <= hoje + timedelta(days=7)

        if self.filtro_periodo == "MES":
            return venc.year == hoje.year and venc.month == hoje.month

        if self.filtro_periodo == "ANO":
            return venc.year == hoje.year

        return True

    def _renderizar_lista(self):

        while self.lista_layout.count():
            item = self.lista_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()

        if self.filtro_status == "TODAS":
            contas_filtradas = [
                c for c in self.contas
                if c.get("status") != "CANCELADO"
            ]
        else:
            contas_filtradas = [
                c for c in self.contas
                if _status_real(c) == self.filtro_status
            ]

        contas_filtradas = [
            c for c in contas_filtradas if self._dentro_do_periodo(c)
        ]

        categoria_selecionada = self.combo_categoria.currentText()
        if categoria_selecionada and categoria_selecionada != "Todas as categorias":
            contas_filtradas = [
                c for c in contas_filtradas
                if c.get("categoria") == categoria_selecionada
            ]

        texto = self.pesquisa.text().lower().strip()
        if texto:
            contas_filtradas = [
                c for c in contas_filtradas
                if texto in str(c.get("descricao") or "").lower()
                or texto in str(c.get("categoria") or "").lower()
            ]

        self.lbl_contagem.setText(
            "1 conta" if len(contas_filtradas) == 1
            else f"{len(contas_filtradas)} contas"
        )

        if not contas_filtradas:

            lbl_vazio = QLabel(
                "Nenhuma conta encontrada com esses filtros."
                if self.contas else
                "Nenhuma conta cadastrada ainda. Clique em \"Nova despesa\" "
                "pra lançar a primeira."
            )
            lbl_vazio.setAlignment(Qt.AlignCenter)
            lbl_vazio.setStyleSheet(f"""
                color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_BASE}px;
                padding:48px; background:transparent;
            """)
            self.lista_layout.addWidget(lbl_vazio)
            return

        # blocos por urgência: o que está vencido aparece primeiro e as
        # pagas por último (antes era só por data, e as pagas antigas
        # ficavam no topo, empurrando as vencidas pra baixo)
        grupos = {}
        for conta in contas_filtradas:
            grupos.setdefault(_grupo_da_conta(conta), []).append(conta)

        for chave, titulo, cor in _GRUPOS:

            contas_grupo = grupos.get(chave)
            if not contas_grupo:
                continue

            contas_grupo.sort(
                key=lambda c: c.get("data_vencimento", ""),
                reverse=(chave in ("PAGAS", "CANCELADAS")),
            )

            self.lista_layout.addWidget(
                self._cabecalho_grupo(titulo, getattr(tokens, cor), contas_grupo)
            )

            for conta in contas_grupo:

                linha = DespesaLinha(conta)
                linha.editar_solicitado.connect(self.editar_despesa)
                linha.excluir_solicitado.connect(self.excluir_despesa)
                linha.pagar_solicitado.connect(self.pagar_despesa)
                linha.duplicar_solicitado.connect(self.duplicar_despesa)
                linha.ver_documento_solicitado.connect(self.ver_documento)
                linha.ver_comprovante_solicitado.connect(self.ver_comprovante)

                self.lista_layout.addWidget(linha)

    def _cabecalho_grupo(self, titulo, cor, contas):

        total = sum(float(c.get("valor", 0) or 0) for c in contas)

        cab = QWidget()
        cab.setStyleSheet(f"background:{tokens.FUNDO};")
        lay = QHBoxLayout(cab)
        # mesmas margens/colunas da DespesaLinha (borda 4 + margem 16 à
        # esquerda; à direita: margem 16, menu 30, botão Pagar 96 e os
        # dois espaçamentos de 14) -- o total cai embaixo dos valores
        lay.setContentsMargins(20, 8, 16, 8)
        lay.setSpacing(0)

        lbl = QLabel(f"{titulo.upper()}  ·  {len(contas)}")
        lbl.setStyleSheet(f"""
            background:transparent; color:{cor};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800; letter-spacing:0.5px;
        """)
        lbl_total = QLabel(formatar_moeda(total))
        lbl_total.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)
        lay.addWidget(lbl)
        lay.addStretch()
        lay.addWidget(lbl_total)
        # alinha o total do grupo com a coluna de valores das linhas
        lay.addSpacing(14 + 96 + 14 + 30)
        return cab

    # ==========================================
    # AÇÕES
    # ==========================================

    def nova_despesa(self):

        dialogo = CadastroDespesaDialog(parent=self)

        if dialogo.exec() == dialogo.DialogCode.Accepted:
            self.carregar()

    def editar_despesa(self, conta):

        dialogo = CadastroDespesaDialog(conta=conta, parent=self)

        if dialogo.exec() == dialogo.DialogCode.Accepted:
            self.carregar()

    def duplicar_despesa(self, conta):

        dialogo = CadastroDespesaDialog(duplicar_de=conta, parent=self)

        if dialogo.exec() == dialogo.DialogCode.Accepted:
            self.carregar()

    def excluir_despesa(self, conta):

        resposta = QMessageBox.question(
            self,
            "Excluir despesa",
            f"Excluir a despesa \"{conta.get('descricao')}\"?",
        )

        if resposta != QMessageBox.Yes:
            return

        rodar_em_thread(
            self,
            excluir_conta_pagar,
            conta["id"],
            ao_sucesso=self._ao_excluir_despesa_sucesso,
            ao_erro=self._ao_excluir_despesa_erro,
        )

    def _ao_excluir_despesa_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_excluir_despesa_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def pagar_despesa(self, conta):

        dialogo = PagamentoDespesaDialog(conta, parent=self)

        if dialogo.exec() == dialogo.DialogCode.Accepted:
            self.carregar()

    def ver_documento(self, conta):

        response = obter_documento_conta_pagar(conta["id"])

        if response.status_code != 200:
            QMessageBox.warning(
                self, "Atenção", "Não foi possível abrir o documento."
            )
            return

        nome_original = conta.get("documento_nome") or "documento"
        extensao = os.path.splitext(nome_original)[1] or ".pdf"

        arquivo_temp = tempfile.NamedTemporaryFile(
            delete=False, suffix=extensao
        )
        arquivo_temp.write(response.content)
        arquivo_temp.close()

        QDesktopServices.openUrl(QUrl.fromLocalFile(arquivo_temp.name))

    def ver_comprovante(self, conta):

        response = obter_comprovante_pagamento_conta_pagar(conta["id"])

        if response.status_code != 200:
            QMessageBox.warning(
                self, "Atenção", "Não foi possível abrir o comprovante."
            )
            return

        nome_original = (
            conta.get("comprovante_pagamento_nome") or "comprovante"
        )
        extensao = os.path.splitext(nome_original)[1] or ".pdf"

        arquivo_temp = tempfile.NamedTemporaryFile(
            delete=False, suffix=extensao
        )
        arquivo_temp.write(response.content)
        arquivo_temp.close()

        QDesktopServices.openUrl(QUrl.fromLocalFile(arquivo_temp.name))
