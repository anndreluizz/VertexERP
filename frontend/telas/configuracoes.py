import base64

from PySide6.QtCore import Qt, QSize, Signal, QBuffer, QIODevice
from PySide6.QtGui import QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QScrollArea,
    QStackedWidget,
    QMessageBox,
    QKeySequenceEdit,
    QCheckBox,
    QSpinBox,
    QFileDialog,
    QComboBox,
    QRadioButton,
    QButtonGroup,
)

from services.api import configuracoes, atualizar_configuracoes, me
from services import preferencias_service
from services import impressora_termica_service
from services import loja_service
from services.comprovante_service import obter_logo_loja
from services.worker import rodar_em_thread
from telas.gerenciar_usuarios import GerenciarUsuariosDialog

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import BotaoPrimario, BotaoSecundario, BotaoSucesso, CampoTexto
from utils.validacao import email_valido
from widgets.fields.cpf_field import CpfCnpjField
from widgets.fields.phone_field import PhoneField
from widgets.fields.email_field import EmailField


class ItemMenuConfig(QPushButton):

    def __init__(self, icone_nome, texto, habilitado=True):

        super().__init__(texto if habilitado else f"{texto}  ·  em breve")

        self.setCheckable(True)
        self.setEnabled(habilitado)
        self.setMinimumHeight(44)
        self.setCursor(
            Qt.PointingHandCursor if habilitado else Qt.ArrowCursor
        )

        cor_icone = tokens.TEXTO_SECUNDARIO if habilitado else tokens.TEXTO_TERCIARIO
        self.setIcon(icone(icone_nome, cor=cor_icone, tamanho=17))
        self.setIconSize(QSize(17, 17))

        if habilitado:
            self.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; text-align:left; padding-left:12px;
                    border:none; border-radius:{tokens.RADIUS_SM}px;
                    color:{tokens.TEXTO_SECUNDARIO}; font-size:{tokens.TAMANHO_SM}px;
                }}
                QPushButton:hover {{ background:{tokens.FUNDO}; }}
                QPushButton:checked {{
                    background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA};
                    font-weight:700;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; text-align:left; padding-left:12px;
                    border:none; border-radius:{tokens.RADIUS_SM}px;
                    color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_SM}px;
                }}
            """)


class Configuracoes(QWidget):

    voltar = Signal()
    loja_atualizada = Signal(str)

    def __init__(self):
        super().__init__()

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
        self.bt_voltar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        titulo = QLabel("Configurações")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        bt_usuarios = BotaoSecundario("Gerenciar Usuários", icone_nome="user")
        bt_usuarios.clicked.connect(self.abrir_gerenciar_usuarios)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addSpacing(4)
        cabecalho.addWidget(titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(bt_usuarios)

        layout.addLayout(cabecalho)

        # ======================
        # CORPO (submenu + conteúdo)
        # ======================

        corpo = QHBoxLayout()
        corpo.setSpacing(20)

        # ---- submenu de categorias ----

        submenu_frame = QFrame()
        submenu_frame.setFixedWidth(280)
        submenu_frame.setStyleSheet(f"""
            background:{tokens.CARD}; border-radius:{tokens.RADIUS_LG}px;
            border:1px solid {tokens.BORDA};
        """)

        submenu_layout = QVBoxLayout(submenu_frame)
        submenu_layout.setContentsMargins(10, 10, 10, 10)
        submenu_layout.setSpacing(4)

        self.bt_gerais = ItemMenuConfig("store", "Configurações Gerais")
        self.bt_pix = ItemMenuConfig("credit-card", "Pagamentos / PIX")
        self.bt_atalhos = ItemMenuConfig("shopping-cart", "Atalhos do PDV")
        self.bt_whatsapp = ItemMenuConfig("message-circle", "WhatsApp")
        self.bt_email_config = ItemMenuConfig("mail", "E-mail (SMTP)")
        self.bt_impressora = ItemMenuConfig("printer", "Impressora / Cupom")
        self.bt_hardware = ItemMenuConfig("settings", "Hardware / Scanner")
        self.bt_lojas = ItemMenuConfig("truck", "Lojas e Filiais")

        itens_futuros = [
            ItemMenuConfig("gift", "Fidelidade e Marketing", habilitado=False),
            ItemMenuConfig("refresh-cw", "Integrações (TEF/POS)", habilitado=False),
            ItemMenuConfig("lock", "Privacidade & LGPD", habilitado=False),
        ]

        submenu_layout.addWidget(self.bt_gerais)
        submenu_layout.addWidget(self.bt_pix)
        submenu_layout.addWidget(self.bt_atalhos)
        submenu_layout.addWidget(self.bt_whatsapp)
        submenu_layout.addWidget(self.bt_email_config)
        submenu_layout.addWidget(self.bt_impressora)
        submenu_layout.addWidget(self.bt_hardware)
        submenu_layout.addWidget(self.bt_lojas)

        for item in itens_futuros:
            submenu_layout.addWidget(item)

        submenu_layout.addStretch()

        self.bt_gerais.clicked.connect(
            lambda: self._selecionar_aba(0)
        )
        self.bt_pix.clicked.connect(lambda: self._selecionar_aba(1))
        self.bt_atalhos.clicked.connect(lambda: self._selecionar_aba(2))
        self.bt_whatsapp.clicked.connect(lambda: self._selecionar_aba(3))
        self.bt_email_config.clicked.connect(lambda: self._selecionar_aba(4))
        self.bt_impressora.clicked.connect(lambda: self._selecionar_aba(5))
        self.bt_hardware.clicked.connect(lambda: self._selecionar_aba(6))
        self.bt_lojas.clicked.connect(lambda: self._selecionar_aba(7))

        corpo.addWidget(submenu_frame)

        # ---- conteúdo ----

        self.paginas = QStackedWidget()

        self.paginas.addWidget(self._criar_pagina_gerais())
        self.paginas.addWidget(self._criar_pagina_pix())
        self.paginas.addWidget(self._criar_pagina_atalhos())
        self.paginas.addWidget(self._criar_pagina_whatsapp())
        self.paginas.addWidget(self._criar_pagina_email())
        self.paginas.addWidget(self._criar_pagina_impressora())
        self.paginas.addWidget(self._criar_pagina_hardware())
        self.paginas.addWidget(self._criar_pagina_lojas())

        corpo.addWidget(self.paginas, stretch=1)

        layout.addLayout(corpo, stretch=1)

        self.bt_gerais.setChecked(True)

        # ======================
        # RODAPÉ
        # ======================

        rodape_layout = QHBoxLayout()
        rodape_layout.addStretch()

        self.bt_salvar = BotaoSucesso("Salvar Alterações")
        self.bt_salvar.setMinimumHeight(46)
        self.bt_salvar.clicked.connect(self.salvar)

        rodape_layout.addWidget(self.bt_salvar)

        layout.addLayout(rodape_layout)

        self.carregar()

    # ======================================

    def _selecionar_aba(self, indice):

        self.bt_gerais.setChecked(indice == 0)
        self.bt_pix.setChecked(indice == 1)
        self.bt_atalhos.setChecked(indice == 2)
        self.bt_whatsapp.setChecked(indice == 3)
        self.bt_email_config.setChecked(indice == 4)
        self.bt_impressora.setChecked(indice == 5)
        self.bt_hardware.setChecked(indice == 6)
        self.bt_lojas.setChecked(indice == 7)

        self.paginas.setCurrentIndex(indice)

    def _criar_pagina_gerais(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = QLabel("DADOS DA LOJA")
        lbl_secao.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.PRIMARIA};
        """)
        layout.addWidget(lbl_secao)

        linha_logo = QHBoxLayout()
        linha_logo.setSpacing(14)

        self.logo_bytes = None

        self.lbl_logo = QLabel()
        self.lbl_logo.setFixedSize(80, 80)
        self.lbl_logo.setAlignment(Qt.AlignCenter)
        self._exibir_logo_padrao()

        col_logo = QVBoxLayout()
        col_logo.setSpacing(6)

        bt_escolher_logo = BotaoSecundario("Escolher Logo", icone_nome="package")
        bt_escolher_logo.setMinimumHeight(38)
        bt_escolher_logo.clicked.connect(self.escolher_logo)

        dica_logo = QLabel("Aparece no cabeçalho dos comprovantes de venda.")
        dica_logo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col_logo.addWidget(bt_escolher_logo)
        col_logo.addWidget(dica_logo)

        linha_logo.addWidget(self.lbl_logo)
        linha_logo.addLayout(col_logo)
        linha_logo.addStretch()

        layout.addLayout(linha_logo)

        self.nome_loja = self._campo(
            layout, "NOME DA LOJA", "Ex: Loja do João"
        )
        self.cnpj_cpf = self._campo(
            layout, "CNPJ / CPF", "000.000.000-00", cls=CpfCnpjField
        )
        self.endereco = self._campo(
            layout, "ENDEREÇO", "Rua, número, bairro, cidade"
        )
        self.telefone = self._campo(
            layout, "TELEFONE", "(00) 00000-0000", cls=PhoneField
        )

        layout.addStretch()

        return self._envolver_com_rolagem(pagina)

    def _envolver_com_rolagem(self, pagina):
        """Em telas mais baixas, o conteúdo de uma aba (campos +
        eventual botão próprio, como o 'Salvar Atalhos') pode não caber
        na altura disponível — sem isso, a parte de baixo simplesmente
        ficava fora da área visível, sem nenhuma forma de rolar até
        ela."""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        scroll.setWidget(pagina)

        return scroll

    def _criar_pagina_pix(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = QLabel("RECEBIMENTO VIA PIX")
        lbl_secao.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.PRIMARIA};
        """)
        layout.addWidget(lbl_secao)

        self.pix_chave = self._campo(
            layout, "CHAVE PIX", "CPF, e-mail, telefone ou aleatória"
        )
        self.pix_nome = self._campo(
            layout, "NOME DO TITULAR (PIX)", "Nome que aparece no PIX"
        )
        self.pix_cidade = self._campo(
            layout, "CIDADE (PIX)", "Cidade do titular"
        )

        dica = QLabel(
            "Esses dados aparecem no QR Code de cobrança gerado "
            "na tela de pagamento."
        )
        dica.setWordWrap(True)
        dica.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(dica)

        layout.addStretch()

        return self._envolver_com_rolagem(pagina)

    def _criar_pagina_atalhos(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = QLabel("ATALHOS DE TECLADO DO PDV")
        lbl_secao.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.PRIMARIA};
        """)
        layout.addWidget(lbl_secao)

        self.atalho_busca = self._campo_atalho(layout, "PESQUISAR PRODUTO (padrão: F1)")
        self.atalho_cadastro = self._campo_atalho(layout, "NOVO PRODUTO (padrão: F4)")
        self.atalho_cancelar = self._campo_atalho(layout, "CANCELAR VENDA (padrão: Esc)")

        dica = QLabel(
            '"Pagar" continua fixo em F3 nesta versão. As mudanças '
            "valem só pra o usuário logado, e aparecem na próxima vez "
            "que o PDV for aberto."
        )
        dica.setWordWrap(True)
        dica.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(dica)

        bt_salvar_atalhos = BotaoSucesso("Salvar Atalhos")
        bt_salvar_atalhos.setMinimumHeight(42)
        bt_salvar_atalhos.clicked.connect(self.salvar_atalhos)
        layout.addWidget(bt_salvar_atalhos)

        layout.addStretch()

        self._carregar_atalhos_ui()

        return self._envolver_com_rolagem(pagina)

    def _criar_pagina_whatsapp(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = QLabel("INTEGRAÇÃO COM WHATSAPP (VIA Z-API)")
        lbl_secao.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.PRIMARIA};
        """)
        layout.addWidget(lbl_secao)

        dica_topo = QLabel(
            "Crie uma conta grátis em z-api.io, escaneie o QR Code com "
            "o WhatsApp que vai mandar as mensagens, e cole aqui o "
            "Instance ID e o Token gerados por lá."
        )
        dica_topo.setWordWrap(True)
        dica_topo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(dica_topo)

        self.whatsapp_instance_id = self._campo(
            layout, "INSTANCE ID", "Ex: 3D9F2A1B8C7E6..."
        )
        self.whatsapp_token = self._campo(
            layout, "TOKEN", "Deixe em branco pra manter o token atual"
        )
        self.whatsapp_token.setEchoMode(QLineEdit.Password)

        self.whatsapp_ativo = QCheckBox("Ativar integração com WhatsApp")
        self.whatsapp_ativo.setStyleSheet(self._estilo_checkbox())
        layout.addWidget(self.whatsapp_ativo)

        linha_divisoria = QFrame()
        linha_divisoria.setFixedHeight(1)
        linha_divisoria.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(linha_divisoria)

        lbl_automacoes = QLabel("AUTOMAÇÕES")
        lbl_automacoes.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.PRIMARIA};
        """)
        layout.addWidget(lbl_automacoes)

        self.whatsapp_lembrete_fiado_ativo = QCheckBox(
            "Lembrar cliente com fiado parado"
        )
        self.whatsapp_lembrete_fiado_ativo.setStyleSheet(self._estilo_checkbox())
        layout.addWidget(self.whatsapp_lembrete_fiado_ativo)

        linha_dias = QHBoxLayout()
        lbl_dias = QLabel("Avisar depois de quantos dias parado:")
        lbl_dias.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO};
        """)
        self.whatsapp_lembrete_fiado_dias = QSpinBox()
        self.whatsapp_lembrete_fiado_dias.setRange(1, 365)
        self.whatsapp_lembrete_fiado_dias.setValue(30)
        self.whatsapp_lembrete_fiado_dias.setMinimumHeight(36)
        self.whatsapp_lembrete_fiado_dias.setStyleSheet(f"""
            QSpinBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 8px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
        """)
        linha_dias.addWidget(lbl_dias)
        linha_dias.addWidget(self.whatsapp_lembrete_fiado_dias)
        linha_dias.addStretch()
        layout.addLayout(linha_dias)

        self.whatsapp_comprovante_venda_ativo = QCheckBox(
            "Mandar comprovante da venda automaticamente pro cliente"
        )
        self.whatsapp_comprovante_venda_ativo.setStyleSheet(self._estilo_checkbox())
        layout.addWidget(self.whatsapp_comprovante_venda_ativo)

        layout.addStretch()

        return self._envolver_com_rolagem(pagina)

    def _criar_pagina_email(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = QLabel("ENVIO DE E-MAIL (SMTP)")
        lbl_secao.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.PRIMARIA};
        """)
        layout.addWidget(lbl_secao)

        dica_topo = QLabel(
            "Use os dados de SMTP do seu provedor de e-mail (Gmail, "
            "Outlook, etc). No Gmail, é preciso gerar uma 'senha de "
            "app' — a senha normal da conta não funciona aqui."
        )
        dica_topo.setWordWrap(True)
        dica_topo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(dica_topo)

        self.smtp_host = self._campo(
            layout, "SERVIDOR SMTP", "Ex: smtp.gmail.com"
        )
        self.smtp_porta = QSpinBox()
        self.smtp_porta.setRange(1, 65535)
        self.smtp_porta.setValue(587)
        self.smtp_porta.setMinimumHeight(42)
        self.smtp_porta.setStyleSheet(f"""
            QSpinBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 8px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
        """)
        lbl_porta = QLabel("PORTA")
        lbl_porta.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(lbl_porta)
        layout.addWidget(self.smtp_porta)

        self.smtp_usuario = self._campo(
            layout, "USUÁRIO (E-MAIL)", "seuemail@gmail.com", cls=EmailField
        )

        self.smtp_senha = self._campo(
            layout, "SENHA", "Deixe em branco pra manter a senha atual"
        )
        self.smtp_senha.setEchoMode(QLineEdit.Password)

        self.smtp_remetente = self._campo(
            layout, "REMETENTE (OPCIONAL)", "Se vazio, usa o usuário acima"
        )

        self.smtp_ativo = QCheckBox("Ativar envio de comprovante por e-mail")
        self.smtp_ativo.setStyleSheet(self._estilo_checkbox())
        layout.addWidget(self.smtp_ativo)

        layout.addStretch()

        return self._envolver_com_rolagem(pagina)

    def _criar_pagina_impressora(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = QLabel("IMPRESSORA TÉRMICA (CUPOM)")
        lbl_secao.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.PRIMARIA};
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

        return self._envolver_com_rolagem(pagina)

    def _criar_pagina_hardware(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = QLabel("LEITOR DE CÓDIGO DE BARRAS")
        lbl_secao.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.PRIMARIA};
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

        return self._envolver_com_rolagem(pagina)

    def _criar_pagina_lojas(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # ---- loja deste terminal ----

        lbl_terminal = QLabel("Loja deste terminal")
        lbl_terminal.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.PRIMARIA};
        """)
        layout.addWidget(lbl_terminal)

        dica_terminal = QLabel(
            "Toda venda, movimento de caixa e ajuste de estoque feito "
            "neste computador é registrado nessa loja — não importa "
            "qual usuário estiver logado. Configure uma vez por "
            "instalação."
        )
        dica_terminal.setWordWrap(True)
        dica_terminal.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO}; line-height:1.5;
        """)
        layout.addWidget(dica_terminal)

        linha_terminal = QHBoxLayout()
        linha_terminal.setSpacing(10)

        self.combo_loja_terminal = QComboBox()
        self.combo_loja_terminal.setMinimumHeight(44)
        self.combo_loja_terminal.setCursor(Qt.PointingHandCursor)
        self.combo_loja_terminal.setStyleSheet(f"""
            QComboBox {{
                border:1.5px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:0 12px; font-size:{tokens.TAMANHO_MD}px; color:{tokens.TEXTO};
            }}
        """)

        bt_salvar_loja_terminal = BotaoPrimario("Salvar")
        bt_salvar_loja_terminal.setMinimumHeight(44)
        bt_salvar_loja_terminal.clicked.connect(self._salvar_loja_do_terminal)

        linha_terminal.addWidget(self.combo_loja_terminal, stretch=1)
        linha_terminal.addWidget(bt_salvar_loja_terminal)

        layout.addLayout(linha_terminal)

        linha_divisoria = QFrame()
        linha_divisoria.setFixedHeight(1)
        linha_divisoria.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(linha_divisoria)

        # ---- lojas cadastradas ----

        lbl_cadastradas = QLabel("Lojas cadastradas")
        lbl_cadastradas.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(lbl_cadastradas)

        self.lista_lojas = QVBoxLayout()
        self.lista_lojas.setSpacing(6)
        layout.addLayout(self.lista_lojas)

        linha_nova_loja = QHBoxLayout()
        linha_nova_loja.setSpacing(10)

        self.campo_nova_loja = CampoTexto("Ex: Filial Centro")
        self.campo_nova_loja.returnPressed.connect(self._criar_loja)

        bt_criar_loja = BotaoSucesso("+ Adicionar")
        bt_criar_loja.clicked.connect(self._criar_loja)

        linha_nova_loja.addWidget(self.campo_nova_loja, stretch=1)
        linha_nova_loja.addWidget(bt_criar_loja)

        layout.addLayout(linha_nova_loja)

        layout.addStretch()

        self._carregar_lojas()

        return self._envolver_com_rolagem(pagina)

    def _carregar_lojas(self):

        rodar_em_thread(
            self,
            loja_service.listar_lojas,
            ao_sucesso=self._ao_carregar_lojas_sucesso,
            ao_erro=self._ao_carregar_lojas_erro,
        )

    def _ao_carregar_lojas_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar as lojas.\n{erro}")

    def _ao_carregar_lojas_sucesso(self, lojas):

        while self.lista_lojas.count():
            item = self.lista_lojas.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.combo_loja_terminal.blockSignals(True)
        self.combo_loja_terminal.clear()
        self.combo_loja_terminal.addItem("(usar a loja do usuário)", None)

        loja_atual = preferencias_service.carregar_loja_id()

        for loja in lojas:

            self.combo_loja_terminal.addItem(loja["nome"], loja["id"])

            if loja_atual == loja["id"]:
                self.combo_loja_terminal.setCurrentIndex(
                    self.combo_loja_terminal.count() - 1
                )

            lbl_loja = QLabel(f"•  {loja['nome']}")
            lbl_loja.setStyleSheet(f"""
                background:transparent; font-size:{tokens.TAMANHO_SM}px;
                color:{tokens.TEXTO};
            """)
            self.lista_lojas.addWidget(lbl_loja)

        self.combo_loja_terminal.blockSignals(False)

        if not lojas:
            lbl_vazio = QLabel("Nenhuma loja cadastrada ainda.")
            lbl_vazio.setStyleSheet(f"""
                background:transparent; font-size:{tokens.TAMANHO_SM}px;
                color:{tokens.TEXTO_TERCIARIO};
            """)
            self.lista_lojas.addWidget(lbl_vazio)

    def _salvar_loja_do_terminal(self):

        loja_id = self.combo_loja_terminal.currentData()

        preferencias_service.salvar_loja_id(loja_id)

        QMessageBox.information(
            self,
            "Salvo",
            "Este terminal já está configurado. Vendas, caixa e "
            "estoque feitos aqui vão contar pra "
            f"\"{self.combo_loja_terminal.currentText()}\".",
        )

    def _criar_loja(self):

        nome = self.campo_nova_loja.text().strip()

        if not nome:
            return

        rodar_em_thread(
            self,
            loja_service.criar_loja,
            nome,
            ao_sucesso=self._ao_criar_loja_sucesso,
            ao_erro=self._ao_criar_loja_erro,
        )

    def _ao_criar_loja_sucesso(self, response):

        if response.status_code != 200:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        self.campo_nova_loja.clear()
        self._carregar_lojas()

    def _ao_criar_loja_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _exibir_logo_padrao(self):

        self.lbl_logo.setPixmap(QPixmap())
        self.lbl_logo.setText("Sem\nlogo")
        self.lbl_logo.setStyleSheet(f"""
            background:{tokens.FUNDO}; color:{tokens.TEXTO_TERCIARIO};
            border:1px dashed {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
            font-size:{tokens.TAMANHO_XS}px;
        """)

    def _comprimir_imagem(self, caminho, lado_maximo=640, qualidade=82):
        """Mesmo motivo de cadastro_produto.py::_comprimir_imagem --
        uma foto de celular sem redimensionar pode passar de varios MB
        e ia inteira pro banco/pro corpo do request."""

        pixmap = QPixmap(caminho)

        if pixmap.isNull():
            return None

        if pixmap.width() > lado_maximo or pixmap.height() > lado_maximo:
            pixmap = pixmap.scaled(
                lado_maximo, lado_maximo,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )

        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "JPEG", qualidade)

        return bytes(buffer.data())

    def escolher_logo(self):

        caminho, _ = QFileDialog.getOpenFileName(
            self, "Escolher Logo", "", "Imagens (*.jpg *.jpeg *.png)"
        )

        if not caminho:
            return

        imagem_comprimida = self._comprimir_imagem(caminho)

        if imagem_comprimida is None:
            QMessageBox.warning(
                self, "Imagem inválida",
                "Não foi possível abrir essa imagem.",
            )
            return

        self.logo_bytes = imagem_comprimida

        pixmap = QPixmap()
        pixmap.loadFromData(self.logo_bytes)

        self.lbl_logo.setStyleSheet("background:transparent; border:none;")
        self.lbl_logo.setPixmap(
            pixmap.scaled(
                80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )

    def _estilo_checkbox(self):
        return f"""
            QCheckBox {{
                background:transparent; font-size:{tokens.TAMANHO_SM}px;
                color:{tokens.TEXTO}; spacing:8px;
            }}
        """

    def _campo_atalho(self, layout, rotulo):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        campo = QKeySequenceEdit()
        campo.setMinimumHeight(42)
        campo.setStyleSheet(f"""
            QKeySequenceEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
        """)

        layout.addWidget(lbl)
        layout.addWidget(campo)

        return campo

    def _carregar_atalhos_ui(self):

        usuario_id = (me() or {}).get("id")
        salvo = preferencias_service.carregar(usuario_id, "pdv_atalhos", {}) or {}

        self.atalho_busca.setKeySequence(QKeySequence(salvo.get("busca", "F1")))
        self.atalho_cadastro.setKeySequence(
            QKeySequence(salvo.get("cadastro_rapido", "F4"))
        )
        self.atalho_cancelar.setKeySequence(
            QKeySequence(salvo.get("cancelar", "Esc"))
        )

    def salvar_atalhos(self):

        teclas = {
            "busca": self.atalho_busca.keySequence().toString() or "F1",
            "cadastro_rapido": self.atalho_cadastro.keySequence().toString() or "F4",
            "cancelar": self.atalho_cancelar.keySequence().toString() or "Esc",
        }

        if len(set(teclas.values())) < len(teclas):
            QMessageBox.warning(
                self, "Atenção", "Cada atalho precisa usar uma tecla diferente."
            )
            return

        usuario_id = (me() or {}).get("id")
        preferencias_service.salvar(usuario_id, "pdv_atalhos", teclas)

        QMessageBox.information(
            self,
            "Salvo",
            "Atalhos salvos. Vão valer na próxima vez que você abrir o PDV.",
        )

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

        self._atualizar_visibilidade_impressora()

    def _config_impressora_termica_atual(self):

        return {
            "ativa": self.impressora_ativa.isChecked(),
            "tipo": "usb" if self.impressora_conexao_usb.isChecked() else "rede",
            "ip": self.impressora_ip.text().strip() or None,
            "porta": self.impressora_porta.value(),
            "nome_impressora_windows": self.impressora_usb.currentText().strip() or None,
            "largura_papel": self.impressora_largura_papel.currentData(),
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

    def _campo(self, layout, rotulo, placeholder, cls=None):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        if cls is None:
            campo = QLineEdit()
            campo.setPlaceholderText(placeholder)
            campo.setMinimumHeight(42)
            campo.setStyleSheet(f"""
                QLineEdit {{
                    border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                    padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                    background: {tokens.CARD};
                }}
                QLineEdit:focus {{ border: 1.5px solid {tokens.PRIMARIA}; }}
            """)
        else:
            # cls (CpfCnpjField/PhoneField/EmailField) já traz sua
            # própria máscara/validação e estilo (baseado em
            # CampoTexto) -- não sobrescrever por cima.
            campo = cls(placeholder)

        layout.addWidget(lbl)
        layout.addWidget(campo)

        return campo

    # ======================================

    def abrir_gerenciar_usuarios(self):

        dialogo = GerenciarUsuariosDialog(parent=self)
        dialogo.exec()

    # ======================================

    def carregar(self):

        rodar_em_thread(
            self,
            configuracoes,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
        )

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar as configurações.\n{erro}"
        )

    def _ao_carregar_sucesso(self, dados):

        self.nome_loja.setText(dados.get("nome_loja") or "")
        self.cnpj_cpf.setText(dados.get("cnpj_cpf") or "")
        self.endereco.setText(dados.get("endereco") or "")
        self.telefone.setText(dados.get("telefone") or "")
        self.pix_chave.setText(dados.get("pix_chave") or "")
        self.pix_nome.setText(dados.get("pix_nome") or "")
        self.pix_cidade.setText(dados.get("pix_cidade") or "")

        self.whatsapp_instance_id.setText(dados.get("whatsapp_instance_id") or "")
        # token nunca volta do backend por segurança -- fica em branco;
        # so e enviado de novo se o usuario digitar um novo aqui
        # (mesmo padrao do smtp_senha logo abaixo)
        self.whatsapp_token.setText("")
        self.whatsapp_ativo.setChecked(bool(dados.get("whatsapp_ativo")))
        self.whatsapp_lembrete_fiado_ativo.setChecked(
            bool(dados.get("whatsapp_lembrete_fiado_ativo"))
        )
        self.whatsapp_lembrete_fiado_dias.setValue(
            dados.get("whatsapp_lembrete_fiado_dias") or 30
        )
        self.whatsapp_comprovante_venda_ativo.setChecked(
            bool(dados.get("whatsapp_comprovante_venda_ativo"))
        )

        self.smtp_host.setText(dados.get("smtp_host") or "")
        self.smtp_porta.setValue(dados.get("smtp_porta") or 587)
        self.smtp_usuario.setText(dados.get("smtp_usuario") or "")
        # senha nunca volta do backend por segurança -- fica em branco;
        # so e enviada de novo se o usuario digitar uma nova aqui
        self.smtp_senha.setText("")
        self.smtp_remetente.setText(dados.get("smtp_remetente") or "")
        self.smtp_ativo.setChecked(bool(dados.get("smtp_ativo")))

        if dados.get("tem_logo"):
            rodar_em_thread(
                self,
                obter_logo_loja,
                ao_sucesso=self._ao_carregar_logo_sucesso,
            )

    def _ao_carregar_logo_sucesso(self, logo_bytes):
        if logo_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(logo_bytes)
            self.lbl_logo.setStyleSheet("background:transparent; border:none;")
            self.lbl_logo.setPixmap(
                pixmap.scaled(
                    80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )

    def salvar(self):

        if not email_valido(self.smtp_usuario.text()):
            QMessageBox.warning(
                self,
                "Atenção",
                "Informe um e-mail válido no campo Usuário (E-mail) do SMTP.",
            )
            self._selecionar_aba(4)
            return

        dados = {
            "nome_loja": self.nome_loja.text().strip() or None,
            "cnpj_cpf": self.cnpj_cpf.text().strip() or None,
            "endereco": self.endereco.text().strip() or None,
            "telefone": self.telefone.text().strip() or None,
            "pix_chave": self.pix_chave.text().strip() or None,
            "pix_nome": self.pix_nome.text().strip() or None,
            "pix_cidade": self.pix_cidade.text().strip() or None,
            "whatsapp_instance_id": self.whatsapp_instance_id.text().strip() or None,
            "whatsapp_ativo": self.whatsapp_ativo.isChecked(),
            "whatsapp_lembrete_fiado_ativo": self.whatsapp_lembrete_fiado_ativo.isChecked(),
            "whatsapp_lembrete_fiado_dias": self.whatsapp_lembrete_fiado_dias.value(),
            "whatsapp_comprovante_venda_ativo": self.whatsapp_comprovante_venda_ativo.isChecked(),
            "smtp_host": self.smtp_host.text().strip() or None,
            "smtp_porta": self.smtp_porta.value(),
            "smtp_usuario": self.smtp_usuario.text().strip() or None,
            "smtp_remetente": self.smtp_remetente.text().strip() or None,
            "smtp_ativo": self.smtp_ativo.isChecked(),
        }

        # so manda a senha se o usuario digitou uma nova -- senao nem
        # inclui a chave no payload, pra nao sobrescrever a senha ja
        # salva com vazio (ver ConfiguracaoUpdate/atualizar no backend)
        senha_digitada = self.smtp_senha.text().strip()
        if senha_digitada:
            dados["smtp_senha"] = senha_digitada

        # mesmo raciocinio pro token do WhatsApp -- so manda se o
        # usuario digitou um novo, senao nao inclui no payload
        token_digitado = self.whatsapp_token.text().strip()
        if token_digitado:
            dados["whatsapp_token"] = token_digitado

        if self.logo_bytes:
            dados["logo_base64"] = base64.b64encode(self.logo_bytes).decode("ascii")

        self.bt_salvar.setEnabled(False)
        self._salvar_dados_pendente = dados

        rodar_em_thread(
            self,
            atualizar_configuracoes,
            dados,
            ao_sucesso=self._ao_salvar_sucesso,
            ao_erro=self._ao_salvar_erro,
            ao_finalizar=self._ao_salvar_finalizado,
        )

    def _ao_salvar_sucesso(self, response):

        dados = self._salvar_dados_pendente

        if response.status_code == 200:

            self.loja_atualizada.emit(dados["nome_loja"] or "Vertex ERP")

            QMessageBox.information(
                self,
                "Sucesso",
                "Configurações salvas com sucesso.",
            )

        else:

            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_salvar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_salvar_finalizado(self):
        self.bt_salvar.setEnabled(True)
