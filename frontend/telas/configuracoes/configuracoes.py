import base64

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QScrollArea,
    QMessageBox,
    QCheckBox,
    QSpinBox,
)

from services.api import configuracoes, atualizar_configuracoes, usuario_e_admin
from services.comprovante_service import obter_logo_loja
from services.worker import rodar_em_thread
from telas.gerenciar_usuarios import GerenciarUsuariosDialog

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import (
    BotaoSecundario, BotaoSucesso, CampoTexto, PilhaPaginas, estilo_checkbox,
)
from utils.validacao import email_valido
from telas.configuracoes.backup import BackupMixin
from telas.configuracoes.comum import ItemMenuConfig, _SECOES, _SECOES_DO_RODAPE
from telas.configuracoes.impressora import ImpressoraMixin
from telas.configuracoes.lojas import LojasMixin
from telas.configuracoes.paginas import PaginasMixin


class Configuracoes(PaginasMixin, ImpressoraMixin, LojasMixin, BackupMixin, QWidget):

    voltar = Signal()
    loja_atualizada = Signal(str)

    def __init__(self):
        super().__init__()

        self._backups_carregados = False
        self._carregando_backups = False
        self._pasta_backups_atual = None

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        # a página inteira rola: em tela de 900px de altura ela não cabia
        # e empurrava a janela principal pra baixo da barra de tarefas
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rolagem.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        conteudo = QWidget()
        conteudo.setStyleSheet(f"background:{tokens.FUNDO};")
        rolagem.setWidget(conteudo)
        externo.addWidget(rolagem)

        layout = QVBoxLayout(conteudo)
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
        self.bt_voltar.clicked.connect(self._voltar)

        titulo = QLabel("Configurações")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        subtitulo = QLabel("Ajustes da loja e do sistema")
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO}; font-weight:700;
        """)
        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)
        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        bt_usuarios = BotaoSecundario("Gerenciar Usuários", icone_nome="user")
        bt_usuarios.clicked.connect(self.abrir_gerenciar_usuarios)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addSpacing(4)
        cabecalho.addLayout(col_titulo)
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
        submenu_frame.setObjectName("submenuConfig")
        submenu_frame.setFixedWidth(260)
        submenu_frame.setStyleSheet(f"""
            QFrame#submenuConfig {{
                background:{tokens.CARD}; border-radius:{tokens.RADIUS_LG}px;
                border:1px solid {tokens.BORDA};
            }}
        """)

        submenu_layout = QVBoxLayout(submenu_frame)
        submenu_layout.setContentsMargins(10, 10, 10, 10)
        submenu_layout.setSpacing(4)

        self.bt_gerais = ItemMenuConfig("store", "Dados da loja")
        self.bt_pix = ItemMenuConfig("credit-card", "Pagamentos e PIX")
        self.bt_atalhos = ItemMenuConfig("shopping-cart", "Atalhos do PDV")
        self.bt_whatsapp = ItemMenuConfig("message-circle", "WhatsApp")
        self.bt_email_config = ItemMenuConfig("mail", "E-mail")
        self.bt_impressora = ItemMenuConfig("printer", "Impressora e cupom")
        self.bt_hardware = ItemMenuConfig("settings", "Hardware e scanner")
        self.bt_lojas = ItemMenuConfig("truck", "Lojas e filiais")
        self.bt_backup = ItemMenuConfig("download", "Backup")
        self.bt_backup.setVisible(usuario_e_admin())

        # agrupado por assunto; os itens "em breve" (Fidelidade, TEF,
        # LGPD) saíram -- botão que não faz nada só ocupava espaço
        def grupo(texto):
            lbl = QLabel(texto)
            lbl.setStyleSheet(f"""
                background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
                font-weight:800; color:{tokens.TEXTO_TERCIARIO}; letter-spacing:0.6px;
                padding:10px 12px 4px 12px;
            """)
            return lbl

        submenu_layout.addWidget(grupo("LOJA"))
        submenu_layout.addWidget(self.bt_gerais)
        submenu_layout.addWidget(self.bt_lojas)
        submenu_layout.addWidget(grupo("VENDAS"))
        submenu_layout.addWidget(self.bt_pix)
        submenu_layout.addWidget(self.bt_atalhos)
        submenu_layout.addWidget(self.bt_impressora)
        submenu_layout.addWidget(self.bt_hardware)
        submenu_layout.addWidget(grupo("COMUNICAÇÃO"))
        submenu_layout.addWidget(self.bt_whatsapp)
        submenu_layout.addWidget(self.bt_email_config)
        self.lbl_grupo_sistema = grupo("SISTEMA")
        self.lbl_grupo_sistema.setVisible(usuario_e_admin())
        submenu_layout.addWidget(self.lbl_grupo_sistema)
        submenu_layout.addWidget(self.bt_backup)

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
        self.bt_backup.clicked.connect(lambda: self._selecionar_aba(8))

        corpo.addWidget(submenu_frame)

        # ---- conteúdo ----

        self.paginas = PilhaPaginas()

        self.paginas.addWidget(self._criar_pagina_gerais())
        self.paginas.addWidget(self._criar_pagina_pix())
        self.paginas.addWidget(self._criar_pagina_atalhos())
        self.paginas.addWidget(self._criar_pagina_whatsapp())
        self.paginas.addWidget(self._criar_pagina_email())
        self.paginas.addWidget(self._criar_pagina_impressora())
        self.paginas.addWidget(self._criar_pagina_hardware())
        self.paginas.addWidget(self._criar_pagina_lojas())
        self.paginas.addWidget(self._criar_pagina_backup())

        corpo.addWidget(self.paginas, stretch=1)

        layout.addLayout(corpo, stretch=1)

        self.bt_gerais.setChecked(True)

        # ======================
        # RODAPÉ
        # ======================

        self.barra_salvar = QFrame()
        self.barra_salvar.setObjectName("barraSalvar")
        rodape_layout = QHBoxLayout(self.barra_salvar)
        rodape_layout.setContentsMargins(18, 10, 10, 10)
        rodape_layout.setSpacing(10)

        self.lbl_estado = QLabel("")
        rodape_layout.addWidget(self.lbl_estado)
        rodape_layout.addStretch()

        self.bt_descartar = BotaoSecundario("Descartar")
        self.bt_descartar.setMinimumHeight(42)
        self.bt_descartar.clicked.connect(self._descartar)
        rodape_layout.addWidget(self.bt_descartar)

        self.bt_salvar = BotaoSucesso("Salvar alterações", icone_nome="check")
        self.bt_salvar.setMinimumHeight(42)
        self.bt_salvar.setMinimumWidth(200)
        self.bt_salvar.setToolTip("Ctrl+S")
        self.bt_salvar.clicked.connect(self.salvar)
        rodape_layout.addWidget(self.bt_salvar)

        layout.addWidget(self.barra_salvar)

        atalho_salvar = QShortcut(QKeySequence("Ctrl+S"), self)
        atalho_salvar.activated.connect(self._salvar_se_alterado)

        self._alterado = False
        self._carregando_dados = True
        self._ligar_deteccao_alteracao()
        self._atualizar_barra_salvar()

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
        self.bt_backup.setChecked(indice == 8)

        self.paginas.setCurrentIndex(indice)
        self._atualizar_barra_salvar()

        if indice == 8 and not self._backups_carregados:
            self._atualizar_backups()

    def _envolver_com_rolagem(self, pagina, indice=None):
        """Em telas mais baixas, o conteúdo de uma aba (campos +
        eventual botão próprio, como o 'Salvar Atalhos') pode não caber
        na altura disponível — sem isso, a parte de baixo simplesmente
        ficava fora da área visível, sem nenhuma forma de rolar até
        ela."""

        # cada seção vira um cartão branco com título e descrição, como
        # as subtelas -- antes os campos ficavam soltos no fundo bege
        cartao = QFrame()
        cartao.setObjectName("cartaoSecaoConfig")
        cartao.setStyleSheet(f"""
            QFrame#cartaoSecaoConfig {{
                background:{tokens.CARD}; border-radius:{tokens.RADIUS_LG}px;
                border:1px solid {tokens.BORDA};
            }}
        """)
        layout_cartao = QVBoxLayout(cartao)
        layout_cartao.setContentsMargins(28, 22, 28, 24)
        layout_cartao.setSpacing(18)

        if indice is not None:
            icone_nome, titulo, descricao = _SECOES[indice]
            topo = QHBoxLayout()
            topo.setSpacing(12)
            chip = QLabel()
            chip.setFixedSize(44, 44)
            chip.setAlignment(Qt.AlignCenter)
            chip.setStyleSheet(f"""
                background:{tokens.PRIMARIA_CLARA}; border:none; border-radius:{tokens.RADIUS_MD}px;
            """)
            chip.setPixmap(icone_pixmap(icone_nome, cor=tokens.PRIMARIA, tamanho=20))
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl_t = QLabel(titulo)
            lbl_t.setStyleSheet(f"""
                background:transparent; border:none; font-size:{tokens.TAMANHO_LG}px;
                font-weight:800; color:{tokens.TEXTO};
            """)
            lbl_d = QLabel(descricao)
            lbl_d.setStyleSheet(f"""
                background:transparent; border:none; font-size:{tokens.TAMANHO_SM}px;
                color:{tokens.TEXTO_TERCIARIO};
            """)
            col.addWidget(lbl_t)
            col.addWidget(lbl_d)
            topo.addWidget(chip)
            topo.addLayout(col, 1)
            layout_cartao.addLayout(topo)

            separador = QFrame()
            separador.setFixedHeight(1)
            separador.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
            layout_cartao.addWidget(separador)

        pagina.setStyleSheet("background:transparent;")
        layout_cartao.addWidget(pagina, 1)

        envoltorio = QWidget()
        envoltorio.setStyleSheet("background:transparent;")
        layout_env = QVBoxLayout(envoltorio)
        layout_env.setContentsMargins(0, 0, 4, 0)
        layout_env.addWidget(cartao)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        scroll.setWidget(envoltorio)

        return scroll

    def _estilo_checkbox(self):
        # quadradinho visível (o padrão sumia no fundo branco)
        return estilo_checkbox() + f"""
            QCheckBox {{ color:{tokens.TEXTO}; font-size:{tokens.TAMANHO_MD}px; }}
        """

    def _campo(self, layout, rotulo, placeholder, cls=None):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        if cls is None:
            campo = CampoTexto(placeholder)
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

        self._carregando_dados = True
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

        self._carregando_dados = False
        self._alterado = False
        self._atualizar_barra_salvar()

        if dados.get("tem_logo"):
            rodar_em_thread(
                self,
                obter_logo_loja,
                ao_sucesso=self._ao_carregar_logo_sucesso,
            )

    # ======================================
    # ALTERAÇÕES NÃO SALVAS
    # ======================================

    def _campos_do_rodape(self):
        return [
            self.nome_loja, self.cnpj_cpf, self.endereco, self.telefone,
            self.pix_chave, self.pix_nome, self.pix_cidade,
            self.whatsapp_instance_id, self.whatsapp_token, self.whatsapp_ativo,
            self.whatsapp_lembrete_fiado_ativo, self.whatsapp_lembrete_fiado_dias,
            self.whatsapp_comprovante_venda_ativo,
            self.smtp_host, self.smtp_porta, self.smtp_usuario, self.smtp_senha,
            self.smtp_remetente, self.smtp_ativo,
        ]

    def _ligar_deteccao_alteracao(self):
        for campo in self._campos_do_rodape():
            if isinstance(campo, QLineEdit):
                campo.textEdited.connect(self._marcar_alterado)
            elif isinstance(campo, QCheckBox):
                campo.toggled.connect(self._marcar_alterado)
            elif isinstance(campo, QSpinBox):
                campo.valueChanged.connect(self._marcar_alterado)

    def _marcar_alterado(self, *_):
        if self._carregando_dados or self._alterado:
            return
        self._alterado = True
        self._atualizar_barra_salvar()

    def _atualizar_barra_salvar(self):

        # seção com botão próprio (atalhos, impressora...) não usa o
        # rodapé -- ele só fica se tiver coisa por salvar das outras
        secao = self.paginas.currentIndex() if hasattr(self, "paginas") else 0
        self.barra_salvar.setVisible(secao in _SECOES_DO_RODAPE or self._alterado)

        if self._alterado:
            fundo, borda = tokens.ALERTA_CLARO, tokens.ALERTA
            texto = "●  Você tem alterações não salvas"
            cor_texto = tokens.ALERTA_TEXTO
        else:
            fundo, borda = tokens.CARD, tokens.BORDA
            texto = "✓  Tudo salvo"
            cor_texto = tokens.TEXTO_TERCIARIO
        self.barra_salvar.setStyleSheet(f"""
            QFrame#barraSalvar {{
                background:{fundo}; border:1px solid {borda};
                border-radius:{tokens.RADIUS_LG}px;
            }}
        """)
        self.lbl_estado.setText(texto)
        self.lbl_estado.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_MD}px;
            font-weight:700; color:{cor_texto};
        """)
        self.bt_salvar.setEnabled(self._alterado)
        self.bt_descartar.setVisible(self._alterado)

    def _salvar_se_alterado(self):
        if self._alterado and self.bt_salvar.isEnabled():
            self.salvar()

    def _descartar(self):
        self.logo_bytes = None
        self._exibir_logo_padrao()
        self._alterado = False
        self._atualizar_barra_salvar()
        self.carregar()

    def _voltar(self):
        if self._alterado:
            resposta = QMessageBox.question(
                self, "Alterações não salvas",
                "Você mudou configurações e ainda não salvou.\n\n"
                "Sair mesmo assim e perder as alterações?",
            )
            if resposta != QMessageBox.Yes:
                return
            self._descartar()
        self.voltar.emit()

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
            self._alterado = False
            self.logo_bytes = None
            self.smtp_senha.clear()
            self.whatsapp_token.clear()

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
        self._atualizar_barra_salvar()
