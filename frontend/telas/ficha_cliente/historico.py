from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
)
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QMessageBox,
    QInputDialog,
)

from services import api
from services.movimento_fiado_service import (
    editar_movimento,
    excluir_movimento,
)
from services.worker import rodar_em_thread
from design import tokens
from design.icons import icone, icone_pixmap
from utils.formatacao import formatar_moeda
from design.widgets import (
    CampoTexto,
    Card,
)
from telas.ficha_cliente.comum import NOMES_FORMA_FIADO, _parse_data


class HistoricoMixin:
    """Linha do tempo de movimentos do fiado: filtros, rolagem e editar/excluir lancamento."""

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
        elif tipo == "PERDA":
            cor = tokens.ERRO
            icone_nome = "lock"
            rotulo_tipo = "Perda (baixada)"
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
            # um produto por linha, com o valor dele (o total da compra
            # ja' aparece a direita)
            subtotal = item.get("subtotal")
            if subtotal is None:
                partes.append(f"{nome} x{quantidade}")
            else:
                partes.append(f"{nome} x{quantidade} — {formatar_moeda(float(subtotal))}")

        return "\n".join(partes) if partes else descricao

    @staticmethod
    def _e_estorno(mov):
        return (mov.get("descricao") or "").startswith("Estorno")
