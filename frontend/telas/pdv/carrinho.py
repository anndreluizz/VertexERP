from services.worker import rodar_em_thread
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QPixmap,
)
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidgetItem,
)
from design import tokens
from design.icons import icone, icone_pixmap
from utils.formatacao import formatar_moeda
from telas.pdv.comum import _CORES_MONOGRAMA, _baixar_foto_com_id, _parse_valor


class CarrinhoMixin:
    """Carrinho: tabela de itens, quantidade, ultimo item e totais."""

    # ==================================================
    # ATUALIZAR TABELA / TOTAIS
    # ==================================================

    def atualizar_tabela(self):

        self.tabela.setRowCount(len(self.itens))

        alinhado_direita = Qt.AlignRight | Qt.AlignVCenter
        linha_ultimo = None

        for linha, item in enumerate(self.itens):
            subtotal = item["preco"] * item["quantidade"]

            celulas = [
                (f"{linha + 1:03d}", Qt.AlignCenter),
                (item["codigo"], Qt.AlignLeft | Qt.AlignVCenter),
                (item["nome"], Qt.AlignLeft | Qt.AlignVCenter),
                (str(item["quantidade"]), Qt.AlignCenter),
                (formatar_moeda(item["preco"]), alinhado_direita),
                (formatar_moeda(subtotal), alinhado_direita),
            ]

            for coluna, (texto, alinhamento) in enumerate(celulas):
                celula = QTableWidgetItem(texto)
                celula.setTextAlignment(alinhamento)
                if coluna in (2, 5):
                    fonte_celula = celula.font()
                    fonte_celula.setBold(True)
                    celula.setFont(fonte_celula)
                self.tabela.setItem(linha, coluna, celula)

            self.tabela.setCellWidget(linha, 3, self._controle_quantidade(linha, item))
            self.tabela.setCellWidget(linha, 6, self._botao_remover(linha))

            if item["id"] == self._id_ultimo_item:
                linha_ultimo = linha

        if self.itens:
            if linha_ultimo is None:
                linha_ultimo = len(self.itens) - 1
                self._id_ultimo_item = self.itens[-1]["id"]
            self.tabela.selectRow(linha_ultimo)
            self.tabela.scrollToItem(self.tabela.item(linha_ultimo, 0))
        else:
            self._id_ultimo_item = None

        self.pilha_carrinho.setCurrentWidget(
            self.tabela if self.itens else self.pilha_carrinho.widget(0)
        )
        self.bt_limpar_carrinho.setVisible(bool(self.itens))

        self._atualizar_ultimo_item()
        self._recalcular_totais()
        self.campo_codigo.setFocus()

    def _botao_linha(self, icone_nome, dica, ao_clicar, cor=None, cor_hover=None):
        """Botãozinho quadrado sem foco (não rouba o foco do campo de
        código, onde o leitor de código de barras digita)."""

        bt = QPushButton()
        bt.setFixedSize(28, 28)
        bt.setCursor(Qt.PointingHandCursor)
        bt.setFocusPolicy(Qt.NoFocus)
        bt.setToolTip(dica)
        bt.setAccessibleName(dica)
        bt.setIcon(icone(icone_nome, cor=cor or tokens.TEXTO_SECUNDARIO, tamanho=14))
        bt.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{cor_hover or tokens.BORDA}; }}
        """)
        bt.clicked.connect(ao_clicar)
        return bt

    def _celula_centralizada(self, *widgets):
        caixa = QWidget()
        caixa.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(caixa)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.setAlignment(Qt.AlignCenter)
        for w in widgets:
            lay.addWidget(w)
        return caixa

    def _controle_quantidade(self, linha, item):

        lbl = QLabel(str(item["quantidade"]))
        lbl.setMinimumWidth(28)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:700;
        """)
        return self._celula_centralizada(
            self._botao_linha("minus", "Diminuir quantidade",
                              lambda: self.alterar_quantidade(linha, -1)),
            lbl,
            self._botao_linha("plus", "Aumentar quantidade",
                              lambda: self.alterar_quantidade(linha, 1)),
        )

    def _botao_remover(self, linha):
        return self._celula_centralizada(
            self._botao_linha("trash-2", "Remover item",
                              lambda: self.remover_item(linha),
                              cor=tokens.ERRO, cor_hover=tokens.ERRO_CLARO)
        )

    # ==================================================
    # DESTAQUE DO ÚLTIMO ITEM
    # ==================================================

    def _atualizar_ultimo_item(self):

        item = next(
            (i for i in self.itens if i["id"] == self._id_ultimo_item), None
        )

        if item is None:
            self.lbl_ultimo_rotulo.setText("")
            self.lbl_ultimo_nome.setText("Aguardando produto...")
            self.lbl_ultimo_nome.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:24px; font-weight:800;
            """)
            self.lbl_ultimo_conta.setText("")
            self.lbl_ultimo_total.setText("")
            self._exibir_monograma_ultimo(None)
            return

        self.lbl_ultimo_rotulo.setText("ÚLTIMO ITEM")
        self.lbl_ultimo_nome.setText(item["nome"])
        self.lbl_ultimo_nome.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:24px; font-weight:800;
        """)
        self.lbl_ultimo_conta.setText(
            f"{item['quantidade']} × {formatar_moeda(item['preco'])}"
        )
        self.lbl_ultimo_total.setText(
            formatar_moeda(item["preco"] * item["quantidade"])
        )

        foto = self._fotos_cache.get(item["id"])

        if foto:
            self._exibir_foto_ultimo(foto)
            return

        self._exibir_monograma_ultimo(item["nome"])

        if item.get("tem_foto") and item["id"] not in self._fotos_cache:
            # marca como "buscando" pra nao disparar de novo a cada
            # atualizacao enquanto a foto baixa
            self._fotos_cache[item["id"]] = None
            rodar_em_thread(
                self,
                _baixar_foto_com_id,
                item["id"],
                ao_sucesso=self._ao_baixar_foto_ultimo,
                ao_erro=self._ignorar_erro,
            )

    def _ao_baixar_foto_ultimo(self, resultado):

        produto_id, foto = resultado

        if not foto:
            return

        self._fotos_cache[produto_id] = foto

        if produto_id == self._id_ultimo_item:
            self._exibir_foto_ultimo(foto)

    def _exibir_foto_ultimo(self, foto):

        pixmap = QPixmap()

        if not pixmap.loadFromData(foto):
            return

        self.lbl_ultimo_foto.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
        """)
        self.lbl_ultimo_foto.setPixmap(
            pixmap.scaled(86, 86, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def _exibir_monograma_ultimo(self, nome):
        """Inicial colorida quando o produto nao tem foto (mesmo
        principio dos avatares de Clientes Recentes do Dashboard)."""

        self.lbl_ultimo_foto.clear()

        if not nome:
            self.lbl_ultimo_foto.setText("")
            self.lbl_ultimo_foto.setStyleSheet(f"""
                background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
            """)
            self.lbl_ultimo_foto.setPixmap(
                icone_pixmap("shopping-cart", cor=tokens.TEXTO_TERCIARIO, tamanho=32)
            )
            return

        cor = _CORES_MONOGRAMA[sum(ord(c) for c in nome) % len(_CORES_MONOGRAMA)]

        self.lbl_ultimo_foto.setText((nome[:1] or "?").upper())
        self.lbl_ultimo_foto.setStyleSheet(f"""
            background:{cor}; color:white; border-radius:{tokens.RADIUS_SM}px;
            font-size:36px; font-weight:900;
        """)

    def _linha_selecionada(self):

        linhas = self.tabela.selectionModel().selectedRows()

        if linhas:
            return linhas[0].row()

        return len(self.itens) - 1

    def _recalcular_totais(self):

        subtotal = sum(item["preco"] * item["quantidade"] for item in self.itens)

        self.desconto_valor = _parse_valor(self.campo_desconto.text())
        self.acrescimo_valor = _parse_valor(self.campo_acrescimo.text())

        # guarda o valor sem o "piso" em zero -- e' o que de fato vai
        # pro backend (ver finalizar_venda); o max(0, ...) abaixo e' so
        # pra exibicao, senao um desconto digitado errado por engano
        # mostraria "R$ 0,00" como se fosse valido e a venda seria
        # recusada so depois de abrir a tela de pagamento inteira
        self._total_bruto = (
            subtotal - self.desconto_valor + self.acrescimo_valor
        )

        total = max(0.0, self._total_bruto)

        self.lbl_itens_valor.setText(str(len(self.itens)))
        self.lbl_itens_tabela.setText(
            "1 item" if len(self.itens) == 1 else f"{len(self.itens)} itens"
        )
        self.lbl_subtotal_valor.setText(formatar_moeda(subtotal))

        self.lbl_desconto_valor.setText(
            f"- {formatar_moeda(self.desconto_valor)}"
            if self.desconto_valor else formatar_moeda(0)
        )
        self.lbl_desconto_valor.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            color: {tokens.ERRO if self.desconto_valor else tokens.TEXTO};
        """)

        self.lbl_acrescimo_valor.setText(
            f"+ {formatar_moeda(self.acrescimo_valor)}"
            if self.acrescimo_valor else formatar_moeda(0)
        )
        self.lbl_acrescimo_valor.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            color: {tokens.SECUNDARIA if self.acrescimo_valor else tokens.TEXTO};
        """)

        self.total.setText(formatar_moeda(total))

        return total

    # ==================================================
    # QUANTIDADE / REMOVER (item selecionado do cupom)
    # ==================================================

    def alterar_quantidade(self, linha, delta):

        if linha >= len(self.itens):
            return

        item = self.itens[linha]
        nova_quantidade = item["quantidade"] + delta

        if nova_quantidade <= 0:
            self.remover_item(linha)
            return

        estoque = item.get("estoque")

        if delta > 0 and estoque is not None and nova_quantidade > estoque:
            self._mostrar_status_busca(
                f"Estoque insuficiente de {item['nome']} — "
                f"disponível: {estoque}.",
                erro=True,
            )
            return

        item["quantidade"] = nova_quantidade
        self._id_ultimo_item = item["id"]

        self.atualizar_tabela()

    def remover_item(self, linha):

        if linha < 0 or linha >= len(self.itens):
            return

        del self.itens[linha]

        # selecao/destaque vao pro item que ficou no lugar (ou o de
        # cima, se era o ultimo) -- Del seguido de Del vai limpando
        if self.itens:
            self._id_ultimo_item = self.itens[min(linha, len(self.itens) - 1)]["id"]

        self.atualizar_tabela()
