from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QMessageBox,
)

from services.cliente_service import cadastrar_cliente, atualizar_cliente


class CadastroClienteDialog(QDialog):

    def __init__(self, cliente=None, parent=None):

        super().__init__(parent)

        self.cliente = cliente
        self.cliente_salvo = None

        editando = cliente is not None

        self.setWindowTitle(
            "Editar Cliente" if editando else "+ Novo Cliente"
        )
        self.setFixedSize(420, 480)
        self.setStyleSheet("background:white;")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QFrame()
        cabecalho.setStyleSheet("background:#202225;")
        cabecalho.setFixedHeight(70)

        cab_layout = QVBoxLayout(cabecalho)
        cab_layout.setContentsMargins(24, 12, 24, 12)
        cab_layout.setSpacing(2)

        titulo = QLabel(
            "EDITAR CLIENTE" if editando else "+ NOVO CLIENTE"
        )
        titulo.setStyleSheet(
            "background:transparent; color:white; "
            "font-size:16px; font-weight:bold;"
        )

        subtitulo = QLabel(
            "Atualize os dados do cliente"
            if editando
            else "Cadastre o cliente pra liberar o fiado dele"
        )
        subtitulo.setStyleSheet(
            "background:transparent; color:#aaaaaa; font-size:11px;"
        )

        cab_layout.addWidget(titulo)
        cab_layout.addWidget(subtitulo)

        raiz.addWidget(cabecalho)

        # ======================
        # CORPO
        # ======================

        corpo = QVBoxLayout()
        corpo.setContentsMargins(24, 20, 24, 20)
        corpo.setSpacing(14)

        self.nome = self._campo(corpo, "NOME", "Nome completo")
        self.whatsapp = self._campo(
            corpo, "WHATSAPP", "(00) 00000-0000"
        )
        self.cpf = self._campo(corpo, "CPF", "000.000.000-00")
        self.endereco = self._campo(
            corpo, "ENDEREÇO", "Rua, número, bairro"
        )

        corpo.addStretch()

        raiz.addLayout(corpo)

        # ======================
        # RODAPÉ
        # ======================

        rodape = QFrame()
        rodape.setStyleSheet(
            "background:#f4f5f7; border-top:1px solid #e0e0e0;"
        )

        rodape_layout = QHBoxLayout(rodape)
        rodape_layout.setContentsMargins(24, 14, 24, 14)
        rodape_layout.setSpacing(10)

        bt_cancelar = QPushButton("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.setStyleSheet("""
            QPushButton {
                background:white;
                color:#202225;
                border:1px solid #cccccc;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        bt_cancelar.clicked.connect(self.reject)

        self.bt_salvar = QPushButton(
            "Salvar Alterações" if editando else "Cadastrar Cliente"
        )
        self.bt_salvar.setMinimumHeight(46)
        self.bt_salvar.setAutoDefault(False)
        self.bt_salvar.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                font-weight:bold;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        self.bt_salvar.clicked.connect(self.salvar)

        rodape_layout.addWidget(bt_cancelar)
        rodape_layout.addWidget(self.bt_salvar)

        raiz.addWidget(rodape)

        if editando:
            self._preencher(cliente)

        self.nome.setFocus()

    # ======================================

    def _campo(self, layout, rotulo, placeholder):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        campo = QLineEdit()
        campo.setPlaceholderText(placeholder)
        campo.setMinimumHeight(44)
        campo.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
                color: #202225;
            }
            QLineEdit:focus {
                border: 1px solid #2E7D32;
            }
        """)

        layout.addWidget(lbl)
        layout.addWidget(campo)

        return campo

    def _preencher(self, cliente):

        self.nome.setText(cliente.get("nome") or "")
        self.whatsapp.setText(cliente.get("telefone") or "")
        self.cpf.setText(cliente.get("cpf_cnpj") or "")
        self.endereco.setText(cliente.get("endereco") or "")

    # ======================================

    def salvar(self):

        nome = self.nome.text().strip()

        if not nome:
            QMessageBox.warning(
                self,
                "Atenção",
                "Informe o nome do cliente.",
            )
            return

        dados = {
            "nome": nome,
            "telefone": self.whatsapp.text().strip() or None,
            "cpf_cnpj": self.cpf.text().strip() or None,
            "endereco": self.endereco.text().strip() or None,
        }

        if self.cliente:

            dados["ativo"] = self.cliente.get("ativo", True)

            response = atualizar_cliente(
                self.cliente["id"],
                dados,
            )

        else:

            response = cadastrar_cliente(dados)

        if response.status_code in (200, 201):

            self.cliente_salvo = response.json()

            self.accept()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))
