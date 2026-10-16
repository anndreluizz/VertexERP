from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QDateEdit,
    QFrame,
    QMessageBox,
    QSpinBox,
    QWidget,
)

from services.movimento_fiado_service import (
    saldo_cliente,
    listar_movimentos_cliente,
    lancar_fiado_manual,
)
from services import cliente_analise
from services.worker import rodar_em_thread
from design import tokens
from design.icons import icone_pixmap
from utils.formatacao import formatar_moeda
from design.widgets import (
    Avatar,
    Badge,
    BotaoSucesso,
    CampoTexto,
    DialogoPadrao,
)
from telas.ficha_cliente.comum import _botao_data_rapida, _dia_com_hora_atual


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

        data_iso = _dia_com_hora_atual(self.data.date())

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
