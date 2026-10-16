from datetime import datetime

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QDateEdit,
    QPushButton,
    QFrame,
    QMessageBox,
)

from services.movimento_fiado_service import (
    listar_movimentos_cliente,
    registrar_pagamento,
)
from services import cliente_analise
from services import comprovante_service, impressora_termica_service, preferencias_service
from services.worker import rodar_em_thread
from design import tokens
from design.icons import icone
from utils.formatacao import formatar_moeda
from design.widgets import (
    Avatar,
    Badge,
    BotaoSucesso,
    CampoTexto,
    DialogoPadrao,
    estilo_botao_forma,
)
from telas.ficha_cliente.comum import (
    FORMAS_PAGAMENTO,
    _ICONES_FORMA_PAGAMENTO,
    _botao_data_rapida,
    _buscar_dados_recibo_pagamento,
    _dia_com_hora_atual,
)


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

        data_iso = _dia_com_hora_atual(self.data.date())

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

        momento = _dia_com_hora_atual(self.data.date())

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
