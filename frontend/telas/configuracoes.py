from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QKeySequence
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
)

from services.api import configuracoes, atualizar_configuracoes, me
from services import preferencias_service
from telas.gerenciar_usuarios import GerenciarUsuariosDialog

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import BotaoSecundario, BotaoSucesso


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

        itens_futuros = [
            ItemMenuConfig("truck", "Lojas e Filiais", habilitado=False),
            ItemMenuConfig("settings", "Hardware / Scanner", habilitado=False),
            ItemMenuConfig("printer", "Impressora / Cupom", habilitado=False),
            ItemMenuConfig("gift", "Fidelidade e Marketing", habilitado=False),
            ItemMenuConfig("refresh-cw", "Integrações (TEF/POS)", habilitado=False),
            ItemMenuConfig("lock", "Privacidade & LGPD", habilitado=False),
        ]

        submenu_layout.addWidget(self.bt_gerais)
        submenu_layout.addWidget(self.bt_pix)
        submenu_layout.addWidget(self.bt_atalhos)

        for item in itens_futuros:
            submenu_layout.addWidget(item)

        submenu_layout.addStretch()

        self.bt_gerais.clicked.connect(
            lambda: self._selecionar_aba(0)
        )
        self.bt_pix.clicked.connect(lambda: self._selecionar_aba(1))
        self.bt_atalhos.clicked.connect(lambda: self._selecionar_aba(2))

        corpo.addWidget(submenu_frame)

        # ---- conteúdo ----

        self.paginas = QStackedWidget()

        self.paginas.addWidget(self._criar_pagina_gerais())
        self.paginas.addWidget(self._criar_pagina_pix())
        self.paginas.addWidget(self._criar_pagina_atalhos())

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

        self.nome_loja = self._campo(
            layout, "NOME DA LOJA", "Ex: Loja do João"
        )
        self.cnpj_cpf = self._campo(
            layout, "CNPJ / CPF", "00.000.000/0000-00"
        )
        self.endereco = self._campo(
            layout, "ENDEREÇO", "Rua, número, bairro, cidade"
        )
        self.telefone = self._campo(
            layout, "TELEFONE", "(00) 00000-0000"
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

    def _campo(self, layout, rotulo, placeholder):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

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

        layout.addWidget(lbl)
        layout.addWidget(campo)

        return campo

    # ======================================

    def abrir_gerenciar_usuarios(self):

        dialogo = GerenciarUsuariosDialog(parent=self)
        dialogo.exec()

    # ======================================

    def carregar(self):

        dados = configuracoes()

        self.nome_loja.setText(dados.get("nome_loja") or "")
        self.cnpj_cpf.setText(dados.get("cnpj_cpf") or "")
        self.endereco.setText(dados.get("endereco") or "")
        self.telefone.setText(dados.get("telefone") or "")
        self.pix_chave.setText(dados.get("pix_chave") or "")
        self.pix_nome.setText(dados.get("pix_nome") or "")
        self.pix_cidade.setText(dados.get("pix_cidade") or "")

    def salvar(self):

        dados = {
            "nome_loja": self.nome_loja.text().strip() or None,
            "cnpj_cpf": self.cnpj_cpf.text().strip() or None,
            "endereco": self.endereco.text().strip() or None,
            "telefone": self.telefone.text().strip() or None,
            "pix_chave": self.pix_chave.text().strip() or None,
            "pix_nome": self.pix_nome.text().strip() or None,
            "pix_cidade": self.pix_cidade.text().strip() or None,
        }

        response = atualizar_configuracoes(dados)

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
