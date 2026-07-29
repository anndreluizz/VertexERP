from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QStackedWidget,
    QMessageBox,
)

from services.api import configuracoes, atualizar_configuracoes
from telas.gerenciar_usuarios import GerenciarUsuariosDialog


class ItemMenuConfig(QPushButton):

    def __init__(self, icone, texto, habilitado=True):

        super().__init__(f"{icone}  {texto}")

        self.setCheckable(True)
        self.setEnabled(habilitado)
        self.setMinimumHeight(44)
        self.setCursor(
            Qt.PointingHandCursor if habilitado else Qt.ArrowCursor
        )

        if habilitado:
            self.setStyleSheet("""
                QPushButton {
                    background:transparent;
                    text-align:left;
                    padding-left:14px;
                    border:none;
                    border-radius:8px;
                    color:#424242;
                    font-size:13px;
                }
                QPushButton:hover {
                    background:#f4f5f7;
                }
                QPushButton:checked {
                    background:#E3F2FD;
                    color:#1565C0;
                    font-weight:bold;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background:transparent;
                    text-align:left;
                    padding-left:14px;
                    border:none;
                    border-radius:8px;
                    color:#c0c0c0;
                    font-size:13px;
                }
            """)
            self.setText(f"{icone}  {texto}  ·  em breve")


class Configuracoes(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()

        self.bt_voltar = QPushButton("← Voltar")
        self.bt_voltar.setStyleSheet("""
            QPushButton {
                background:transparent;
                color:gray;
                border:none;
                font-size:13px;
            }
            QPushButton:hover {
                color:#202225;
            }
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        titulo = QLabel("Configurações")
        titulo.setStyleSheet(
            "background:transparent; font-size:20px; "
            "font-weight:bold; color:#202225;"
        )

        bt_usuarios = QPushButton("👤 Gerenciar Usuários")
        bt_usuarios.setStyleSheet("""
            QPushButton {
                background:#f4f5f7;
                color:#202225;
                border-radius:8px;
                padding:8px 16px;
                font-weight:bold;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        bt_usuarios.clicked.connect(self.abrir_gerenciar_usuarios)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addSpacing(12)
        cabecalho.addWidget(titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(bt_usuarios)

        layout.addLayout(cabecalho)

        # ======================
        # CORPO (submenu + conteúdo)
        # ======================

        corpo = QHBoxLayout()
        corpo.setSpacing(24)

        # ---- submenu de categorias ----

        submenu_frame = QFrame()
        submenu_frame.setFixedWidth(280)
        submenu_frame.setStyleSheet(
            "background:#fafafa; border-radius:12px; "
            "border:1px solid #eeeeee;"
        )

        submenu_layout = QVBoxLayout(submenu_frame)
        submenu_layout.setContentsMargins(10, 10, 10, 10)
        submenu_layout.setSpacing(4)

        self.bt_gerais = ItemMenuConfig("🏪", "Configurações Gerais")
        self.bt_pix = ItemMenuConfig("⚡", "Pagamentos / PIX")

        itens_futuros = [
            ItemMenuConfig("🏬", "Lojas e Filiais", habilitado=False),
            ItemMenuConfig("🖥", "Hardware / Scanner", habilitado=False),
            ItemMenuConfig("🖨", "Impressora / Cupom", habilitado=False),
            ItemMenuConfig(
                "⭐", "Fidelidade e Marketing", habilitado=False
            ),
            ItemMenuConfig(
                "💳", "Integrações (TEF/POS)", habilitado=False
            ),
            ItemMenuConfig("🛡", "Privacidade & LGPD", habilitado=False),
        ]

        submenu_layout.addWidget(self.bt_gerais)
        submenu_layout.addWidget(self.bt_pix)

        for item in itens_futuros:
            submenu_layout.addWidget(item)

        submenu_layout.addStretch()

        self.bt_gerais.clicked.connect(
            lambda: self._selecionar_aba(0)
        )
        self.bt_pix.clicked.connect(lambda: self._selecionar_aba(1))

        corpo.addWidget(submenu_frame)

        # ---- conteúdo ----

        self.paginas = QStackedWidget()

        self.paginas.addWidget(self._criar_pagina_gerais())
        self.paginas.addWidget(self._criar_pagina_pix())

        corpo.addWidget(self.paginas, stretch=1)

        layout.addLayout(corpo, stretch=1)

        self.bt_gerais.setChecked(True)

        # ======================
        # RODAPÉ
        # ======================

        rodape = QFrame()
        rodape.setStyleSheet(
            "background:#f4f5f7; border-top:1px solid #e0e0e0;"
        )

        rodape_layout = QHBoxLayout(rodape)
        rodape_layout.setContentsMargins(0, 14, 0, 0)

        rodape_layout.addStretch()

        self.bt_salvar = QPushButton("Salvar Alterações")
        self.bt_salvar.setMinimumHeight(46)
        self.bt_salvar.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                font-weight:bold;
                border-radius:10px;
                padding:0 24px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        self.bt_salvar.clicked.connect(self.salvar)

        rodape_layout.addWidget(self.bt_salvar)

        layout.addWidget(rodape)

        self.carregar()

    # ======================================

    def _selecionar_aba(self, indice):

        self.bt_gerais.setChecked(indice == 0)
        self.bt_pix.setChecked(indice == 1)

        self.paginas.setCurrentIndex(indice)

    def _criar_pagina_gerais(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = QLabel("DADOS DA LOJA")
        lbl_secao.setStyleSheet(
            "background:transparent; font-size:12px; "
            "font-weight:bold; color:#1565C0;"
        )
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

        return pagina

    def _criar_pagina_pix(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = QLabel("RECEBIMENTO VIA PIX")
        lbl_secao.setStyleSheet(
            "background:transparent; font-size:12px; "
            "font-weight:bold; color:#1565C0;"
        )
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
            "+ Esses dados aparecem no QR Code de cobrança gerado "
            "na tela de pagamento."
        )
        dica.setWordWrap(True)
        dica.setStyleSheet(
            "background:transparent; font-size:11px; color:gray;"
        )
        layout.addWidget(dica)

        layout.addStretch()

        return pagina

    def _campo(self, layout, rotulo, placeholder):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(
            "background:transparent; font-size:10px; "
            "font-weight:bold; color:gray;"
        )

        campo = QLineEdit()
        campo.setPlaceholderText(placeholder)
        campo.setMinimumHeight(42)
        campo.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
                color: #202225;
            }
            QLineEdit:focus {
                border: 1px solid #2E7D32;
            }
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
