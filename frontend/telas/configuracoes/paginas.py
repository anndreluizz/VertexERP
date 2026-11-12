from PySide6.QtCore import Qt, QBuffer, QIODevice
from PySide6.QtGui import QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QFrame,
    QMessageBox,
    QKeySequenceEdit,
    QSpinBox,
    QFileDialog,
)

from services.api import me
from services import preferencias_service

from design import tokens
from design.widgets import (
    BotaoSecundario, BotaoSucesso,
)
from widgets.fields.cpf_field import CpfCnpjField
from widgets.fields.phone_field import PhoneField
from widgets.fields.email_field import EmailField


class PaginasMixin:
    """Paginas simples: gerais, Pix, atalhos, WhatsApp, e-mail e logo da loja."""

    def _criar_pagina_gerais(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = self._titulo_bloco("DADOS DA LOJA")
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

        return self._envolver_com_rolagem(pagina, 0)

    def _criar_pagina_pix(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = self._titulo_bloco("RECEBIMENTO VIA PIX")
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

        return self._envolver_com_rolagem(pagina, 1)

    def _criar_pagina_atalhos(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = self._titulo_bloco("ATALHOS DE TECLADO DO PDV")
        layout.addWidget(lbl_secao)

        self.atalho_busca = self._campo_atalho(layout, "Pesquisar produto", "Padrão: F1")
        self.atalho_cadastro = self._campo_atalho(layout, "Novo produto", "Padrão: F4")
        self.atalho_cancelar = self._campo_atalho(layout, "Cancelar venda", "Padrão: Esc")

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

        bt_salvar_atalhos = BotaoSucesso("Salvar atalhos")
        bt_salvar_atalhos.setMinimumHeight(42)
        bt_salvar_atalhos.clicked.connect(self.salvar_atalhos)
        layout.addWidget(bt_salvar_atalhos, 0, Qt.AlignRight)

        layout.addStretch()

        self._carregar_atalhos_ui()

        return self._envolver_com_rolagem(pagina, 2)

    def _criar_pagina_whatsapp(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = self._titulo_bloco("INTEGRAÇÃO COM WHATSAPP (VIA Z-API)")
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

        self.whatsapp_ativo = self._interruptor(
            layout, "Ativar integração com WhatsApp", "Liga o envio de mensagens pela Z-API")

        linha_divisoria = QFrame()
        linha_divisoria.setFixedHeight(1)
        linha_divisoria.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(linha_divisoria)

        lbl_automacoes = self._titulo_bloco("AUTOMAÇÕES")
        layout.addWidget(lbl_automacoes)

        self.whatsapp_lembrete_fiado_ativo = self._interruptor(
            layout, "Lembrar cliente com fiado parado", "Manda um lembrete educado pelo WhatsApp")

        self.whatsapp_lembrete_fiado_dias = QSpinBox()
        self.whatsapp_lembrete_fiado_dias.setRange(1, 365)
        self.whatsapp_lembrete_fiado_dias.setValue(60)
        self.whatsapp_lembrete_fiado_dias.setMinimumHeight(36)
        self.whatsapp_lembrete_fiado_dias.setStyleSheet(f"""
            QSpinBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 8px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
        """)
        self.whatsapp_lembrete_fiado_dias.setFixedWidth(110)
        self._linha(layout, "Avisar depois de quantos dias sem pagar", "Conta do último pagamento (sem pagamento, da última compra)", self.whatsapp_lembrete_fiado_dias)

        self.whatsapp_comprovante_venda_ativo = self._interruptor(
            layout, "Mandar comprovante da venda", "Vai sozinho pro WhatsApp do cliente")

        layout.addStretch()

        return self._envolver_com_rolagem(pagina, 3)

    def _criar_pagina_email(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = self._titulo_bloco("ENVIO DE E-MAIL (SMTP)")
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
        self.smtp_porta.setFixedWidth(120)
        self._linha(layout, "Porta", "Gmail e Outlook usam 587", self.smtp_porta)

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

        self.smtp_ativo = self._interruptor(
            layout, "Ativar envio de comprovante por e-mail", "Usa o servidor configurado acima")

        layout.addStretch()

        return self._envolver_com_rolagem(pagina, 4)

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
        self._marcar_alterado()

        pixmap = QPixmap()
        pixmap.loadFromData(self.logo_bytes)

        self.lbl_logo.setStyleSheet("background:transparent; border:none;")
        self.lbl_logo.setPixmap(
            pixmap.scaled(
                80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )

    def _campo_atalho(self, layout, rotulo, ajuda=""):

        campo = QKeySequenceEdit()
        campo.setMinimumHeight(42)
        campo.setStyleSheet(f"""
            QKeySequenceEdit QLineEdit {{
                border: 1.5px solid {tokens.BORDA_FORTE}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD}; min-height: 40px;
            }}
        """)

        campo.setFixedWidth(200)
        return self._linha(layout, rotulo, ajuda, campo)

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
