from datetime import datetime, timedelta

from services.produto_service import (
    listar_produtos,
)
from services.relatorio_service import relatorio_vendas
from services.api import configuracoes
from services import comprovante_service
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import (
    QPixmap,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
)
from design import tokens
from design.fonts import fonte
from design.icons import icone, icone_pixmap
from design.widgets import (
    Badge,
    BotaoSucesso,
    CampoTexto,
)
from utils.formatacao import formatar_moeda


class LayoutMixin:
    """Montagem visual do PDV: cabecalho, atalhos, campo de codigo, cartoes de carrinho e resumo."""

    # ==================================================
    # CONSTRUÇÃO DA INTERFACE
    # ==================================================

    def _construir_cabecalho(self):

        cabecalho = QHBoxLayout()
        cabecalho.setContentsMargins(24, 16, 24, 12)
        cabecalho.setSpacing(10)

        self.bt_voltar = QPushButton()
        self.bt_voltar.setFixedSize(38, 38)
        self.bt_voltar.setCursor(Qt.PointingHandCursor)
        self.bt_voltar.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        self.bt_voltar.setToolTip("Voltar")
        self.bt_voltar.setAccessibleName("Voltar")
        self.bt_voltar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background: {tokens.FUNDO}; }}
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Frente de Caixa")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)

        config = configuracoes()
        nome_loja = config.get("nome_loja") or ""

        # logo da loja no cabecalho -- mesma imagem usada nos
        # comprovantes, pra dar uma cara mais profissional pro PDV
        # (fica de frente pro cliente, no caixa). So aparece se a loja
        # tiver logo cadastrado em Configuracoes.
        self.lbl_logo_pdv = QLabel()
        self.lbl_logo_pdv.setFixedSize(40, 40)
        self.lbl_logo_pdv.setAlignment(Qt.AlignCenter)
        self.lbl_logo_pdv.setStyleSheet("background:transparent; border:none;")
        self.lbl_logo_pdv.setVisible(False)

        logo_bytes = None
        if config.get("tem_logo"):
            try:
                logo_bytes = comprovante_service.obter_logo_loja()
            except Exception:
                # rede/servidor instavel nao pode derrubar a tela do
                # PDV inteira so por causa da logo -- pior caso e' o
                # cabecalho ficar sem ela, igual quando a loja nao tem
                # logo cadastrado
                logo_bytes = None

        if logo_bytes:
            pixmap_logo = QPixmap()
            if pixmap_logo.loadFromData(logo_bytes):
                self.lbl_logo_pdv.setPixmap(
                    pixmap_logo.scaled(
                        40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                )
                self.lbl_logo_pdv.setVisible(True)

        self.lbl_loja = QLabel(nome_loja)
        self.lbl_loja.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(self.lbl_loja)

        self.badge_caixa = Badge("Caixa aberto", "sucesso")

        self.bt_retomar = self._botao_ghost_cabecalho("Vendas Suspensas")
        self.bt_retomar.setEnabled(False)
        self.bt_retomar.clicked.connect(self.abrir_vendas_suspensas)

        self.bt_suspender = self._botao_ghost_cabecalho("Suspender")
        self.bt_suspender.clicked.connect(self.suspender_venda)

        self.bt_orcamento = self._botao_ghost_cabecalho("Orçamento", icone_nome="printer")
        self.bt_orcamento.clicked.connect(self.imprimir_orcamento)

        # contorno vermelho (e não botão vermelho cheio): é uma ação
        # destrutiva e rara -- não pode ser a coisa mais chamativa da
        # tela, competindo com o Finalizar Venda
        self.bt_cancelar = QPushButton("  Cancelar venda")
        self.bt_cancelar.setIcon(icone("x", cor=tokens.ERRO, tamanho=15))
        self.bt_cancelar.setCursor(Qt.PointingHandCursor)
        self.bt_cancelar.setMinimumHeight(38)
        self.bt_cancelar.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{tokens.ERRO};
                border:1.5px solid {tokens.ERRO}; border-radius:{tokens.RADIUS_SM}px;
                padding:0 14px; font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            }}
            QPushButton:hover {{ background:{tokens.ERRO_CLARO}; }}
        """)
        self.bt_cancelar.clicked.connect(self.cancelar_venda)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addWidget(self.lbl_logo_pdv)
        cabecalho.addLayout(col_titulo)
        cabecalho.addSpacing(4)
        cabecalho.addWidget(self.badge_caixa, alignment=Qt.AlignVCenter)

        self.badge_troca = Badge("Troca", "alerta")
        self.badge_troca.setVisible(False)
        cabecalho.addWidget(self.badge_troca, alignment=Qt.AlignVCenter)

        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_retomar)
        cabecalho.addWidget(self.bt_suspender)
        cabecalho.addWidget(self.bt_orcamento)
        cabecalho.addWidget(self.bt_cancelar)

        return cabecalho

    def _botao_ghost_cabecalho(self, texto, icone_nome=None):
        """Botão de ação secundária do cabeçalho sem contorno -- só
        fundo sutil no hover. As 3 ações daqui (Vendas Suspensas,
        Suspender, Orçamento) são usadas bem menos que Cancelar Venda
        e não precisam do mesmo peso visual de um botão contornado
        (pedido direto: menos linha no cabeçalho)."""

        bt = QPushButton(texto)
        bt.setCursor(Qt.PointingHandCursor)
        bt.setMinimumHeight(38)

        if icone_nome:
            bt.setIcon(icone(icone_nome, cor=tokens.TEXTO_SECUNDARIO, tamanho=15))
            bt.setIconSize(QSize(15, 15))

        bt.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; border-radius:{tokens.RADIUS_SM}px;
                padding:0 12px; color:{tokens.TEXTO_SECUNDARIO};
                font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            }}
            QPushButton:hover:enabled {{ background:{tokens.FUNDO}; }}
            QPushButton:disabled {{
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
            }}
        """)

        return bt

    def _construir_barra_atalhos(self):

        barra = QFrame()
        barra.setFixedHeight(42)
        barra.setStyleSheet(f"""
            QFrame {{
                background: {tokens.FUNDO};
                border: none;
            }}
        """)
        # a barra nunca pode ditar a largura minima do PDV -- como todas
        # as telas dividem a mesma janela (QStackedWidget), uma barra
        # comprida aqui alargava o app inteiro alem da tela (1600px)
        barra.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        layout = QHBoxLayout(barra)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        self.lbl_atalho_busca_tecla, item_busca = self._item_atalho(
            self.atalhos["busca"], "Buscar"
        )
        self.lbl_atalho_produto_tecla, item_produto = self._item_atalho(
            self.atalhos["cadastro_rapido"], "Novo produto"
        )
        _, item_cliente = self._item_atalho("F2", "Cliente")
        _, item_finalizar = self._item_atalho("F3", "Finalizar")
        _, item_desconto = self._item_atalho("F6", "Desconto")
        _, item_acrescimo = self._item_atalho("F7", "Acréscimo")
        _, item_quantidade = self._item_atalho("+ −", "Quantidade")
        _, item_remover = self._item_atalho("Del", "Remover")

        for item in (
            item_busca, item_cliente, item_finalizar,
            item_produto, item_desconto, item_acrescimo,
            item_quantidade, item_remover,
        ):
            layout.addLayout(item)

        layout.addStretch()

        self.lbl_relogio_pdv = QLabel()
        self.lbl_relogio_pdv.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        layout.addWidget(self.lbl_relogio_pdv)

        self._timer_relogio_pdv = QTimer(self)
        self._timer_relogio_pdv.timeout.connect(self._atualizar_relogio_pdv)
        self._timer_relogio_pdv.start(1000)
        self._atualizar_relogio_pdv()

        return barra

    def _item_atalho(self, tecla, rotulo):

        item = QHBoxLayout()
        item.setSpacing(6)

        badge_tecla = QLabel(tecla)
        badge_tecla.setAlignment(Qt.AlignCenter)
        badge_tecla.setFixedHeight(20)
        badge_tecla.setStyleSheet(f"""
            background:{tokens.CARD}; color:{tokens.TEXTO_SECUNDARIO};
            border:none; border-radius:4px;
            font-size:{tokens.TAMANHO_XS}px; font-weight:700; padding: 0 6px;
        """)

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        item.addWidget(badge_tecla)
        item.addWidget(lbl_rotulo)

        return badge_tecla, item

    def _atualizar_relogio_pdv(self):
        self.lbl_relogio_pdv.setText(datetime.now().strftime("%d/%m/%Y  ·  %H:%M"))

    def _construir_campo_codigo(self):

        container = QFrame()
        container.setFixedHeight(58)
        container.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 2px solid {tokens.PRIMARIA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(12)

        self.campo_codigo = QLineEdit()
        self.campo_codigo.setPlaceholderText(
            "Leia o código de barras ou digite o nome  (3* = 3 unidades)"
        )
        self.campo_codigo.setFont(fonte(16))
        self.campo_codigo.setStyleSheet(f"""
            QLineEdit {{
                border: none; outline: none; background: transparent;
                color: {tokens.TEXTO}; font-size: 16px; font-weight: 600;
            }}
        """)
        # ícone desenhado dentro do próprio campo (QLineEdit.addAction)
        # em vez de um QLabel separado ao lado -- evita qualquer
        # contorno/moldura indesejada que um widget irmão poderia
        # ganhar do estilo do Qt quando o campo está focado.
        self.campo_codigo.addAction(
            icone("search", cor=tokens.PRIMARIA, tamanho=20),
            QLineEdit.LeadingPosition,
        )
        self.campo_codigo.returnPressed.connect(self.processar_codigo)
        self.campo_codigo.textChanged.connect(self._atualizar_multiplicador)
        layout.addWidget(self.campo_codigo, stretch=1)

        # "3*" digitado antes do codigo -- mostra que a proxima leitura
        # vai entrar com essa quantidade (ver processar_codigo)
        self.lbl_multiplicador = QLabel()
        self.lbl_multiplicador.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA};
            font-size:{tokens.TAMANHO_MD}px; font-weight:800; border:none;
            border-radius:{tokens.RADIUS_PILL}px; padding: 4px 12px;
        """)
        self.lbl_multiplicador.setVisible(False)
        layout.addWidget(self.lbl_multiplicador)

        # Buscar / Novo produto -- formas alternativas de adicionar
        # item, coladas no campo; discretas porque o caminho principal
        # e' o leitor/teclado (F1/F4)
        estilo_bt_campo = f"""
            QPushButton {{
                background:{tokens.FUNDO}; color:{tokens.TEXTO_SECUNDARIO};
                border:none; border-radius:{tokens.RADIUS_SM}px;
                font-size:{tokens.TAMANHO_SM}px; font-weight:700;
                padding: 0 12px;
            }}
            QPushButton:hover {{ background:{tokens.BORDA}; color:{tokens.TEXTO}; }}
        """

        self.bt_buscar = QPushButton(f"Buscar ({self.atalhos['busca']})")
        self.bt_buscar.setIcon(icone("search", cor=tokens.TEXTO_SECUNDARIO, tamanho=14))
        self.bt_buscar.setCursor(Qt.PointingHandCursor)
        self.bt_buscar.setFixedHeight(36)
        self.bt_buscar.setFocusPolicy(Qt.NoFocus)
        self.bt_buscar.setStyleSheet(estilo_bt_campo)
        self.bt_buscar.clicked.connect(self.abrir_busca)
        layout.addWidget(self.bt_buscar)

        self.bt_adicionar = QPushButton(
            f"Novo Produto ({self.atalhos['cadastro_rapido']})"
        )
        self.bt_adicionar.setIcon(icone("plus", cor=tokens.TEXTO_SECUNDARIO, tamanho=14))
        self.bt_adicionar.setCursor(Qt.PointingHandCursor)
        self.bt_adicionar.setFixedHeight(36)
        self.bt_adicionar.setFocusPolicy(Qt.NoFocus)
        self.bt_adicionar.setStyleSheet(estilo_bt_campo)
        self.bt_adicionar.clicked.connect(self.abrir_novo_produto)
        layout.addWidget(self.bt_adicionar)

        self.lbl_status_busca = QLabel("")
        self.lbl_status_busca.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; padding-left: 4px;
        """)
        # vazio = escondido; senão o QLabel sem texto ainda ocupava uma
        # linha + o espaçamento do layout entre a busca e o cupom
        self.lbl_status_busca.setVisible(False)

        return container

    def _construir_ultimo_item(self):
        """Faixa de destaque do ultimo produto lido (foto ou inicial,
        nome grande, "qtd x unitario" e o total da linha) -- o que o
        operador e o cliente olham pra confirmar que a leitura entrou
        certa, igual aos PDVs de supermercado."""

        self.cartao_ultimo = QFrame()
        self.cartao_ultimo.setObjectName("cartaoUltimoItem")
        self.cartao_ultimo.setFixedHeight(96)
        self.cartao_ultimo.setStyleSheet(f"""
            QFrame#cartaoUltimoItem {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        layout = QHBoxLayout(self.cartao_ultimo)
        layout.setContentsMargins(14, 12, 22, 12)
        layout.setSpacing(16)

        self.lbl_ultimo_foto = QLabel()
        self.lbl_ultimo_foto.setFixedSize(72, 72)
        self.lbl_ultimo_foto.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_ultimo_foto)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(2)

        self.lbl_ultimo_rotulo = QLabel()
        self.lbl_ultimo_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800; letter-spacing:0.5px;
        """)

        self.lbl_ultimo_nome = QLabel()
        self.lbl_ultimo_nome.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:24px; font-weight:800;
        """)

        self.lbl_ultimo_conta = QLabel()
        self.lbl_ultimo_conta.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:600;
        """)

        col_texto.addStretch()
        col_texto.addWidget(self.lbl_ultimo_rotulo)
        col_texto.addWidget(self.lbl_ultimo_nome)
        col_texto.addWidget(self.lbl_ultimo_conta)
        col_texto.addStretch()

        layout.addLayout(col_texto, 1)

        self.lbl_ultimo_total = QLabel()
        self.lbl_ultimo_total.setMinimumWidth(240)
        self.lbl_ultimo_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_ultimo_total.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:30px; font-weight:800;
        """)
        layout.addWidget(self.lbl_ultimo_total)

        self._atualizar_ultimo_item()

        return self.cartao_ultimo

    def _construir_linha_cliente(self):

        linha = QFrame()
        linha.setStyleSheet(f"""
            QFrame {{
                background: {tokens.FUNDO};
                border: none;
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(8)

        lbl_icone = QLabel()
        lbl_icone.setStyleSheet("background:transparent;")
        lbl_icone.setPixmap(icone_pixmap("users", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        layout.addWidget(lbl_icone)

        col_cliente = QVBoxLayout()
        col_cliente.setSpacing(0)

        lbl_rotulo = QLabel("CLIENTE")
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        self.lbl_cliente = QLabel("Nenhum cliente selecionado")
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)

        col_cliente.addWidget(lbl_rotulo)
        col_cliente.addWidget(self.lbl_cliente)

        layout.addLayout(col_cliente)
        layout.addStretch()

        self.bt_limpar_cliente = QPushButton("remover")
        self.bt_limpar_cliente.setCursor(Qt.PointingHandCursor)
        self.bt_limpar_cliente.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.ERRO}; font-size:{tokens.TAMANHO_XS}px;
            }}
        """)
        self.bt_limpar_cliente.clicked.connect(self.limpar_cliente)
        self.bt_limpar_cliente.setVisible(False)
        layout.addWidget(self.bt_limpar_cliente)

        self.bt_selecionar_cliente = QPushButton("F2")
        self.bt_selecionar_cliente.setToolTip("Selecionar cliente (F2)")
        self.bt_selecionar_cliente.setCursor(Qt.PointingHandCursor)
        self.bt_selecionar_cliente.setFocusPolicy(Qt.NoFocus)
        self.bt_selecionar_cliente.setFixedHeight(30)
        self.bt_selecionar_cliente.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; color:{tokens.PRIMARIA};
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                font-size:{tokens.TAMANHO_SM}px; font-weight:800; padding: 0 12px;
            }}
            QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA}; }}
        """)
        self.bt_selecionar_cliente.clicked.connect(self.abrir_selecionar_cliente)
        layout.addWidget(self.bt_selecionar_cliente)

        return linha

    def _construir_mais_vendidos(self):

        self.linha_mais_vendidos = QFrame()
        self.linha_mais_vendidos.setStyleSheet("background:transparent; border:none;")
        self.linha_mais_vendidos.setVisible(False)
        self.linha_mais_vendidos.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        layout = QHBoxLayout(self.linha_mais_vendidos)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(8)

        lbl_icone = QLabel()
        lbl_icone.setStyleSheet("background:transparent;")
        lbl_icone.setPixmap(icone_pixmap("trending-up", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        layout.addWidget(lbl_icone)

        self.lbl_titulo_rapidos = QLabel("Mais vendidos:")
        self.lbl_titulo_rapidos.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        layout.addWidget(self.lbl_titulo_rapidos)

        self.layout_chips_mais_vendidos = QHBoxLayout()
        self.layout_chips_mais_vendidos.setSpacing(6)
        layout.addLayout(self.layout_chips_mais_vendidos)

        layout.addStretch()

        return self.linha_mais_vendidos

    def atualizar_mais_vendidos(self):
        """Painel de acesso rápido pros produtos mais vendidos nos
        últimos 30 dias. Usa o relatório de vendas (top_produtos já vem
        agregado pelo banco) em vez de baixar o histórico de vendas
        inteiro pro cliente e somar em Python -- com muitas vendas
        registradas, aquele caminho antigo deixava a abertura do PDV
        visivelmente lenta."""

        while self.layout_chips_mais_vendidos.count():
            item = self.layout_chips_mais_vendidos.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        hoje = datetime.now().date()
        inicio = hoje - timedelta(days=30)

        try:
            relatorio = relatorio_vendas(
                inicio.isoformat(), hoje.isoformat(), limit=1
            )
            produtos = listar_produtos()
        except Exception:
            self.linha_mais_vendidos.setVisible(False)
            return

        produtos_por_nome = {p["nome"]: p for p in produtos}
        top = relatorio.get("top_produtos", [])[:5]
        rapidos = [
            produtos_por_nome.get(entrada.get("produto")) for entrada in top
        ]
        rapidos = [p for p in rapidos if p and p.get("ativo", True)]

        # loja nova (ou 30 dias sem venda) ainda não tem "mais
        # vendidos" -- usa os produtos marcados como favoritos no
        # cadastro, pra linha de atalhos não nascer vazia
        titulo = "Mais vendidos:"
        if not rapidos:
            rapidos = [
                p for p in produtos if p.get("favorito") and p.get("ativo", True)
            ][:5]
            titulo = "Favoritos:"
        self.lbl_titulo_rapidos.setText(titulo)

        exibidos = 0

        for produto in rapidos:

            nome_chip = produto["nome"]
            if len(nome_chip) > 20:
                nome_chip = nome_chip[:19].rstrip() + "…"
            chip = QPushButton(nome_chip)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setFocusPolicy(Qt.NoFocus)
            chip.setMinimumHeight(32)
            chip.setToolTip(
                f"{produto['nome']} · "
                f"{formatar_moeda(produto.get('preco_efetivo', produto['preco_venda']))}"
            )
            chip.setStyleSheet(f"""
                QPushButton {{
                    background:{tokens.CARD}; color:{tokens.TEXTO};
                    border:1px solid {tokens.BORDA}; border-radius:16px;
                    padding:0 14px; font-size:{tokens.TAMANHO_SM}px; font-weight:600;
                }}
                QPushButton:hover {{
                    border-color:{tokens.PRIMARIA}; color:{tokens.PRIMARIA};
                    background:{tokens.PRIMARIA_CLARA};
                }}
            """)
            chip.clicked.connect(
                lambda _checked, p=produto: self.adicionar_produto_ao_carrinho(
                    {
                        "id": p["id"],
                        "codigo": p["codigo"],
                        "nome": p["nome"],
                        # preco_efetivo (nao preco_venda): respeita a
                        # promocao vigente, igual a busca normal do PDV
                        # -- o backend recusa preco diferente desse
                        "preco": float(p.get("preco_efetivo", p["preco_venda"])),
                        "estoque": p["estoque"],
                    },
                    1,
                )
            )
            # nunca espremer o chip (cortava o texto pela metade): se a
            # janela for estreita, os últimos ficam de fora da área
            chip.setMinimumWidth(chip.sizeHint().width())
            self.layout_chips_mais_vendidos.addWidget(chip)
            exibidos += 1

        self.linha_mais_vendidos.setVisible(exibidos > 0)

    def _construir_cartao_tabela(self):
        """A tabela em si (self.tabela) fica dentro de um Card, mas o
        atributo continua sendo o QTableWidget puro — atualizar_tabela()
        mexe direto nele (setRowCount/setItem/setCellWidget). Alterna
        com um estado vazio (self.pilha_carrinho) quando não há itens,
        pra não deixar um vão em branco atrás da tabela zerada."""

        cartao = QFrame()
        cartao.setObjectName("cartaoCupom")
        cartao.setStyleSheet(f"""
            QFrame#cartaoCupom {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        layout = QVBoxLayout(cartao)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        cabecalho_tabela = QHBoxLayout()
        cabecalho_tabela.setContentsMargins(16, 14, 16, 10)

        lbl_titulo_tabela = QLabel("CUPOM")
        lbl_titulo_tabela.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:800; letter-spacing: 0.5px;
        """)
        cabecalho_tabela.addWidget(lbl_titulo_tabela)
        cabecalho_tabela.addStretch()

        self.lbl_itens_tabela = QLabel("0 itens")
        self.lbl_itens_tabela.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        cabecalho_tabela.addWidget(self.lbl_itens_tabela)

        self.bt_limpar_carrinho = QPushButton("Limpar carrinho")
        self.bt_limpar_carrinho.setCursor(Qt.PointingHandCursor)
        self.bt_limpar_carrinho.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.ERRO}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:600; margin-left: 14px;
            }}
            QPushButton:hover {{ color:{tokens.ERRO_HOVER}; }}
        """)
        # reaproveita cancelar_venda -- mesma confirmacao, mesmo efeito
        # de esvaziar o carrinho; so' um atalho visual mais perto de
        # onde o operador esta' olhando (o contador de itens)
        self.bt_limpar_carrinho.clicked.connect(self.cancelar_venda)
        self.bt_limpar_carrinho.setVisible(False)
        cabecalho_tabela.addWidget(self.bt_limpar_carrinho)

        layout.addLayout(cabecalho_tabela)

        self.pilha_carrinho = QStackedWidget()
        self.pilha_carrinho.setStyleSheet("background:transparent;")

        self.pilha_carrinho.addWidget(self._construir_estado_vazio_carrinho())

        self.tabela = QTableWidget()

        # quantidade e remoção continuam pelo teclado (+ / - / Del no
        # item selecionado, ver eventFilter), e agora também por botões
        # na própria linha pra quem opera com o mouse
        self.tabela.setColumnCount(7)

        self.tabela.setHorizontalHeaderLabels([
            "Nº",
            "Código",
            "Produto",
            "Qtd",
            "Unitário",
            "Total",
            "",
        ])

        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setShowGrid(False)
        self.tabela.verticalHeader().setDefaultSectionSize(48)

        cabecalho_horizontal = self.tabela.horizontalHeader()
        cabecalho_horizontal.setStretchLastSection(False)
        cabecalho_horizontal.setSectionResizeMode(2, QHeaderView.Stretch)
        self.tabela.setColumnWidth(0, 52)
        self.tabela.setColumnWidth(1, 110)
        self.tabela.setColumnWidth(3, 120)
        self.tabela.setColumnWidth(4, 110)
        self.tabela.setColumnWidth(5, 120)
        self.tabela.setColumnWidth(6, 52)
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                border: none;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                font-size: {tokens.TAMANHO_MD}px;
                alternate-background-color: {tokens.FUNDO};
                selection-background-color: {tokens.PRIMARIA_CLARA};
                selection-color: {tokens.TEXTO};
            }}
            QHeaderView::section {{
                background: {tokens.CARD};
                color: {tokens.TEXTO_SECUNDARIO};
                font-weight: 700;
                font-size: {tokens.TAMANHO_XS}px;
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
            QTableWidget::item {{
                border: none;
                padding: 4px;
            }}
        """)
        self.tabela.setAlternatingRowColors(True)

        self.pilha_carrinho.addWidget(self.tabela)
        self.pilha_carrinho.setCurrentIndex(0)

        layout.addWidget(self.pilha_carrinho, stretch=1)

        return cartao

    def _construir_estado_vazio_carrinho(self):

        estado = QWidget()
        estado.setStyleSheet("background:transparent;")

        layout = QVBoxLayout(estado)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        lbl_titulo = QLabel("CAIXA LIVRE")
        lbl_titulo.setAlignment(Qt.AlignCenter)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.SECUNDARIA};
            font-size:40px; font-weight:900; letter-spacing: 3px;
        """)
        layout.addWidget(lbl_titulo)

        lbl_dica = QLabel(
            "Passe o código de barras ou pressione "
            f"{self.atalhos['busca']} para buscar pelo nome."
        )
        lbl_dica.setAlignment(Qt.AlignCenter)
        lbl_dica.setWordWrap(True)
        lbl_dica.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        # largura FIXA (não máxima): com quebra de linha e só largura
        # máxima, o Qt calculava a altura de 1 linha e cortava o resto
        lbl_dica.setFixedWidth(420)
        layout.addWidget(lbl_dica, alignment=Qt.AlignCenter)

        return estado

    def _linha_resumo(self, rotulo):
        """Uma linha "rótulo ..... valor" do card de resumo — devolve o
        QLabel do valor pra poder atualizar depois."""

        linha = QHBoxLayout()
        linha.setSpacing(8)

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        lbl_valor = QLabel("R$ 0,00")
        lbl_valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)

        linha.addWidget(lbl_rotulo)
        linha.addStretch()
        linha.addWidget(lbl_valor)

        return linha, lbl_valor

    def _construir_cartao_resumo(self):

        cartao = QFrame()
        cartao.setObjectName("cartaoResumoVenda")
        cartao.setStyleSheet(f"""
            QFrame#cartaoResumoVenda {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_LG}px;
            }}
        """)

        layout = QVBoxLayout(cartao)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(self._construir_linha_cliente())

        titulo = QLabel("RESUMO DA VENDA")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800; letter-spacing: 0.5px;
        """)
        layout.addWidget(titulo)

        linha_itens, self.lbl_itens_valor = self._linha_resumo("Itens")
        self.lbl_itens_valor.setText("0")
        layout.addLayout(linha_itens)

        linha_subtotal, self.lbl_subtotal_valor = self._linha_resumo("Subtotal")
        layout.addLayout(linha_subtotal)

        # ------ desconto / acréscimo (recolhido por padrão) ------

        linha_ajuste_botoes = QHBoxLayout()
        linha_ajuste_botoes.setSpacing(18)

        estilo_bt_ajuste = f"""
            QPushButton {{
                background:transparent; border:none; text-align:left;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:600; padding: 2px 0;
            }}
        """

        self.bt_alternar_ajuste = QPushButton("+ Desconto (F6)")
        self.bt_alternar_ajuste.setCursor(Qt.PointingHandCursor)
        self.bt_alternar_ajuste.setStyleSheet(estilo_bt_ajuste)
        self.bt_alternar_ajuste.clicked.connect(self._alternar_bloco_ajuste)

        self.bt_alternar_acrescimo = QPushButton("+ Acréscimo (F7)")
        self.bt_alternar_acrescimo.setCursor(Qt.PointingHandCursor)
        self.bt_alternar_acrescimo.setStyleSheet(estilo_bt_ajuste)
        self.bt_alternar_acrescimo.clicked.connect(self._abrir_ajuste_acrescimo)

        linha_ajuste_botoes.addWidget(self.bt_alternar_ajuste)
        linha_ajuste_botoes.addWidget(self.bt_alternar_acrescimo)
        linha_ajuste_botoes.addStretch()

        layout.addLayout(linha_ajuste_botoes)

        self.bloco_ajuste = QFrame()
        self.bloco_ajuste.setVisible(False)
        self.bloco_ajuste.setStyleSheet(f"""
            QFrame {{
                background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
            }}
        """)

        ajuste_layout = QHBoxLayout(self.bloco_ajuste)
        ajuste_layout.setContentsMargins(14, 12, 14, 12)
        ajuste_layout.setSpacing(12)

        col_desconto = QVBoxLayout()
        col_desconto.setSpacing(4)
        lbl_desconto = QLabel("DESCONTO (R$)")
        lbl_desconto.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        self.campo_desconto = CampoTexto("0,00")
        self.campo_desconto.textChanged.connect(self._recalcular_totais)
        col_desconto.addWidget(lbl_desconto)
        col_desconto.addWidget(self.campo_desconto)

        col_acrescimo = QVBoxLayout()
        col_acrescimo.setSpacing(4)
        lbl_acrescimo = QLabel("ACRÉSCIMO (R$)")
        lbl_acrescimo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        self.campo_acrescimo = CampoTexto("0,00")
        self.campo_acrescimo.textChanged.connect(self._recalcular_totais)
        col_acrescimo.addWidget(lbl_acrescimo)
        col_acrescimo.addWidget(self.campo_acrescimo)

        ajuste_layout.addLayout(col_desconto)
        ajuste_layout.addLayout(col_acrescimo)

        layout.addWidget(self.bloco_ajuste)

        linha_desconto, self.lbl_desconto_valor = self._linha_resumo("Desconto")
        layout.addLayout(linha_desconto)

        linha_acrescimo, self.lbl_acrescimo_valor = self._linha_resumo("Acréscimo")
        layout.addLayout(linha_acrescimo)

        # total ancorado embaixo, colado no botao Finalizar -- o espaco
        # que sobra fica entre o detalhamento e o total
        layout.addStretch()

        caixa_total = QFrame()
        caixa_total.setStyleSheet(f"""
            QFrame {{
                background: {tokens.SUCESSO_CLARO};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

        layout_caixa_total = QVBoxLayout(caixa_total)
        layout_caixa_total.setContentsMargins(16, 14, 16, 16)
        layout_caixa_total.setSpacing(2)

        lbl_total_rotulo = QLabel("TOTAL")
        lbl_total_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800; letter-spacing: 0.5px;
        """)
        layout_caixa_total.addWidget(lbl_total_rotulo)

        self.total = QLabel("R$ 0,00")
        self.total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.total.setStyleSheet(f"""
            background:transparent; font-size: 40px; font-weight: 900;
            color: {tokens.SECUNDARIA};
        """)
        layout_caixa_total.addWidget(self.total)

        layout.addWidget(caixa_total)

        return cartao

    def _construir_botao_pagar(self):

        self.bt_pagar = BotaoSucesso("Finalizar Venda (F3)", icone_nome="credit-card")
        self.bt_pagar.setMinimumHeight(58)
        self.bt_pagar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.bt_pagar.clicked.connect(self.finalizar_venda)

        return self.bt_pagar
