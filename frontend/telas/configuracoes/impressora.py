from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QMessageBox,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QRadioButton,
    QButtonGroup,
)

from services import preferencias_service
from services import impressora_termica_service

from design import tokens
from design.widgets import (
    BotaoSecundario, BotaoSucesso,
)


class ImpressoraMixin:
    """Paginas Impressora e Hardware (impressora termica USB)."""

    def _criar_pagina_impressora(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = QLabel("IMPRESSORA TÉRMICA (CUPOM)")
        lbl_secao.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:800; color:{tokens.TEXTO_SECUNDARIO}; letter-spacing:0.6px;
        """)
        layout.addWidget(lbl_secao)

        dica_topo = QLabel(
            "Manda o comprovante direto no protocolo da impressora "
            "térmica (ESC/POS), sem depender da janela de impressão "
            "do Windows -- resolve o caso mais comum de impressora "
            "térmica genérica que não imprime nada por causa do "
            "driver. Com isso desligado, a impressão continua saindo "
            "pela janela normal do Windows, como sempre."
        )
        dica_topo.setWordWrap(True)
        dica_topo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(dica_topo)

        self.impressora_ativa = QCheckBox(
            "Imprimir comprovantes e extratos direto na impressora térmica"
        )
        self.impressora_ativa.setStyleSheet(self._estilo_checkbox())
        self.impressora_ativa.toggled.connect(self._atualizar_visibilidade_impressora)
        layout.addWidget(self.impressora_ativa)

        linha_conexao = QHBoxLayout()
        self.impressora_conexao_rede = QRadioButton("Rede (Wi-Fi/Ethernet)")
        self.impressora_conexao_usb = QRadioButton("USB")
        self.impressora_conexao_rede.setChecked(True)

        grupo_conexao = QButtonGroup(self)
        grupo_conexao.addButton(self.impressora_conexao_rede)
        grupo_conexao.addButton(self.impressora_conexao_usb)

        self.impressora_conexao_rede.toggled.connect(
            self._atualizar_visibilidade_impressora
        )

        linha_conexao.addWidget(self.impressora_conexao_rede)
        linha_conexao.addWidget(self.impressora_conexao_usb)
        linha_conexao.addStretch()
        layout.addLayout(linha_conexao)

        # ---- bloco rede ----

        self.impressora_bloco_rede = QWidget()
        layout_rede = QVBoxLayout(self.impressora_bloco_rede)
        layout_rede.setContentsMargins(0, 0, 0, 0)
        layout_rede.setSpacing(10)

        self.impressora_ip = self._campo(
            layout_rede, "IP DA IMPRESSORA", "Ex: 192.168.0.50"
        )

        lbl_porta = QLabel("PORTA")
        lbl_porta.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        self.impressora_porta = QSpinBox()
        self.impressora_porta.setRange(1, 65535)
        self.impressora_porta.setValue(9100)
        self.impressora_porta.setMinimumHeight(42)
        self.impressora_porta.setStyleSheet(f"""
            QSpinBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 8px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
        """)
        layout_rede.addWidget(lbl_porta)
        layout_rede.addWidget(self.impressora_porta)

        layout.addWidget(self.impressora_bloco_rede)

        # ---- bloco usb ----

        self.impressora_bloco_usb = QWidget()
        layout_usb = QVBoxLayout(self.impressora_bloco_usb)
        layout_usb.setContentsMargins(0, 0, 0, 0)
        layout_usb.setSpacing(10)

        lbl_usb = QLabel("IMPRESSORA (INSTALADA NO WINDOWS)")
        lbl_usb.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        self.impressora_usb = QComboBox()
        self.impressora_usb.setEditable(True)
        self.impressora_usb.setMinimumHeight(42)
        self.impressora_usb.setStyleSheet(f"""
            QComboBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
        """)

        bt_atualizar_usb = BotaoSecundario("Atualizar lista", icone_nome="refresh-cw")
        bt_atualizar_usb.setMinimumHeight(38)
        bt_atualizar_usb.clicked.connect(self._carregar_impressoras_usb)

        layout_usb.addWidget(lbl_usb)
        layout_usb.addWidget(self.impressora_usb)
        layout_usb.addWidget(bt_atualizar_usb)

        layout.addWidget(self.impressora_bloco_usb)

        # ---- papel ----

        lbl_papel = QLabel("LARGURA DO PAPEL")
        lbl_papel.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        self.impressora_largura_papel = QComboBox()
        self.impressora_largura_papel.addItem("80mm", 80)
        self.impressora_largura_papel.addItem("58mm", 58)
        self.impressora_largura_papel.setMinimumHeight(42)
        self.impressora_largura_papel.setStyleSheet(f"""
            QComboBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
        """)
        layout.addWidget(lbl_papel)
        layout.addWidget(self.impressora_largura_papel)

        # ---- vias ----

        lbl_vias = QLabel("VIAS (VENDA E RECIBO DE PAGAMENTO)")
        lbl_vias.setStyleSheet(lbl_papel.styleSheet())
        self.impressora_vias = QComboBox()
        self.impressora_vias.addItem("1 via", 1)
        self.impressora_vias.addItem("2 vias (cliente + loja)", 2)
        self.impressora_vias.setMinimumHeight(42)
        self.impressora_vias.setStyleSheet(self.impressora_largura_papel.styleSheet())
        layout.addWidget(lbl_vias)
        layout.addWidget(self.impressora_vias)

        linha_botoes = QHBoxLayout()
        linha_botoes.setSpacing(10)

        bt_testar_impressora = BotaoSecundario("Testar Impressão", icone_nome="printer")
        bt_testar_impressora.setMinimumHeight(42)
        bt_testar_impressora.clicked.connect(self.testar_impressora_termica)

        bt_salvar_impressora = BotaoSucesso("Salvar Configuração da Impressora")
        bt_salvar_impressora.setMinimumHeight(42)
        bt_salvar_impressora.clicked.connect(self.salvar_impressora_termica)

        linha_botoes.addWidget(bt_testar_impressora)
        linha_botoes.addWidget(bt_salvar_impressora)
        layout.addLayout(linha_botoes)

        layout.addStretch()

        self._carregar_impressoras_usb()
        self._carregar_impressora_termica_ui()
        self._atualizar_visibilidade_impressora()

        return self._envolver_com_rolagem(pagina, 5)

    def _criar_pagina_hardware(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = QLabel("LEITOR DE CÓDIGO DE BARRAS")
        lbl_secao.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:800; color:{tokens.TEXTO_SECUNDARIO}; letter-spacing:0.6px;
        """)
        layout.addWidget(lbl_secao)

        dica_usb = QLabel(
            "Leitores USB ou Bluetooth do tipo \"pistola\" (a grande "
            "maioria vendida hoje) já funcionam com o Vertex sem "
            "precisar instalar nada nem configurar aqui — eles se "
            "comportam como um teclado: ao bipar, o código aparece "
            "digitado sozinho onde o cursor estiver."
        )
        dica_usb.setWordWrap(True)
        dica_usb.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO}; line-height:1.5;
        """)
        layout.addWidget(dica_usb)

        lbl_onde = QLabel("ONDE USAR")
        lbl_onde.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(lbl_onde)

        dica_onde = QLabel(
            "• PDV: clique no campo de código de barras (o campo "
            "grande no topo da tela de vendas) e bipe — o produto é "
            "adicionado ao carrinho automaticamente.\n\n"
            "• Cadastro de Produto: o campo \"Código de barras\" já "
            "vem com o foco pronto para bipar — a busca acontece "
            "sozinha enquanto o código é digitado/bipado."
        )
        dica_onde.setWordWrap(True)
        dica_onde.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO}; line-height:1.5;
        """)
        layout.addWidget(dica_onde)

        linha_divisoria = QFrame()
        linha_divisoria.setFixedHeight(1)
        linha_divisoria.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(linha_divisoria)

        lbl_problema = QLabel("SE O LEITOR NÃO FUNCIONAR")
        lbl_problema.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(lbl_problema)

        dica_problema = QLabel(
            "Abra o Bloco de Notas do Windows e bipe um código lá — "
            "se os números não aparecerem digitados, o problema é do "
            "leitor/Windows, não do Vertex (confira o manual do "
            "leitor: a maioria tem um modo \"USB HID\"/\"teclado\" que "
            "precisa estar ativo, geralmente configurado bipando um "
            "código especial que vem no manual)."
        )
        dica_problema.setWordWrap(True)
        dica_problema.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO}; line-height:1.5;
        """)
        layout.addWidget(dica_problema)

        linha_divisoria2 = QFrame()
        linha_divisoria2.setFixedHeight(1)
        linha_divisoria2.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(linha_divisoria2)

        lbl_camera = QLabel("LEITURA PELA CÂMERA")
        lbl_camera.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(lbl_camera)

        dica_camera = QLabel(
            "Ainda não disponível — por enquanto, use um leitor "
            "USB/Bluetooth ou digite o código manualmente."
        )
        dica_camera.setWordWrap(True)
        dica_camera.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(dica_camera)

        layout.addStretch()

        return self._envolver_com_rolagem(pagina, 6)

    # ======================================
    # IMPRESSORA TÉRMICA
    # ======================================

    def _atualizar_visibilidade_impressora(self):

        ativa = self.impressora_ativa.isChecked()
        modo_rede = self.impressora_conexao_rede.isChecked()

        self.impressora_conexao_rede.setEnabled(ativa)
        self.impressora_conexao_usb.setEnabled(ativa)
        self.impressora_bloco_rede.setVisible(ativa and modo_rede)
        self.impressora_bloco_usb.setVisible(ativa and not modo_rede)

    def _carregar_impressoras_usb(self):

        atual = self.impressora_usb.currentText()

        self.impressora_usb.clear()
        self.impressora_usb.addItems(impressora_termica_service.listar_impressoras_windows())

        indice = self.impressora_usb.findText(atual)
        if indice >= 0:
            self.impressora_usb.setCurrentIndex(indice)
        elif atual:
            self.impressora_usb.setEditText(atual)

    def _carregar_impressora_termica_ui(self):

        salvo = preferencias_service.carregar_impressora_termica() or {}

        self.impressora_ativa.setChecked(bool(salvo.get("ativa")))

        if salvo.get("tipo") == "usb":
            self.impressora_conexao_usb.setChecked(True)
        else:
            self.impressora_conexao_rede.setChecked(True)

        self.impressora_ip.setText(salvo.get("ip") or "")
        self.impressora_porta.setValue(salvo.get("porta") or 9100)

        nome_usb = salvo.get("nome_impressora_windows")
        if nome_usb:
            indice = self.impressora_usb.findText(nome_usb)
            if indice >= 0:
                self.impressora_usb.setCurrentIndex(indice)
            else:
                self.impressora_usb.setEditText(nome_usb)

        largura = salvo.get("largura_papel") or 80
        indice_papel = self.impressora_largura_papel.findData(largura)
        if indice_papel >= 0:
            self.impressora_largura_papel.setCurrentIndex(indice_papel)

        indice_vias = self.impressora_vias.findData(salvo.get("vias") or 1)
        if indice_vias >= 0:
            self.impressora_vias.setCurrentIndex(indice_vias)

        self._atualizar_visibilidade_impressora()

    def _config_impressora_termica_atual(self):

        return {
            "ativa": self.impressora_ativa.isChecked(),
            "tipo": "usb" if self.impressora_conexao_usb.isChecked() else "rede",
            "ip": self.impressora_ip.text().strip() or None,
            "porta": self.impressora_porta.value(),
            "nome_impressora_windows": self.impressora_usb.currentText().strip() or None,
            "largura_papel": self.impressora_largura_papel.currentData(),
            "vias": self.impressora_vias.currentData(),
        }

    def salvar_impressora_termica(self):

        config = self._config_impressora_termica_atual()

        if config["ativa"] and config["tipo"] == "rede" and not config["ip"]:
            QMessageBox.warning(
                self, "Atenção", "Informe o IP da impressora térmica."
            )
            return

        if (
            config["ativa"] and config["tipo"] == "usb"
            and not config["nome_impressora_windows"]
        ):
            QMessageBox.warning(
                self, "Atenção",
                'Escolha qual impressora instalada no Windows é a '
                'impressora térmica (clique em "Atualizar lista" se '
                "não aparecer nada).",
            )
            return

        preferencias_service.salvar_impressora_termica(config)

        QMessageBox.information(
            self, "Salvo", "Configuração da impressora térmica salva."
        )

    def testar_impressora_termica(self):

        config = self._config_impressora_termica_atual()

        ok, erro = impressora_termica_service.imprimir_teste(config)

        if ok:
            QMessageBox.information(
                self, "Sucesso",
                "Comando de teste enviado -- confira se saiu no papel.",
            )
        else:
            QMessageBox.critical(self, "Falha", erro)
