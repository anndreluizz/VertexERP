from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QFrame,
    QScrollArea,
    QWidget,
    QMessageBox,
)

from design import tokens
from design.widgets import BotaoPrimario, BotaoSecundario
from services.fornecedor_service import cadastrar_fornecedor, atualizar_fornecedor
from services.worker import rodar_em_thread
from utils.validacao import email_valido
from widgets.fields.cpf_field import CpfCnpjField
from widgets.fields.phone_field import PhoneField
from widgets.fields.email_field import EmailField


class CadastroFornecedorDialog(QDialog):

    def __init__(self, fornecedor=None, parent=None):

        super().__init__(parent)

        self.fornecedor = fornecedor
        self.fornecedor_salvo = None

        editando = fornecedor is not None

        self.setWindowTitle("Editar Fornecedor" if editando else "Novo Fornecedor")
        self.setFixedWidth(440)
        self.resize(440, 600)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        cabecalho = QFrame()
        cabecalho.setStyleSheet(f"background:{tokens.SIDEBAR};")

        cab_layout = QVBoxLayout(cabecalho)
        cab_layout.setContentsMargins(24, 20, 24, 20)
        cab_layout.setSpacing(2)

        titulo = QLabel(
            "EDITAR FORNECEDOR" if editando else "+ NOVO FORNECEDOR"
        )
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_CLARO};
            font-size:{tokens.TAMANHO_LG}px; font-weight:800;
        """)

        subtitulo = QLabel("Usado na importação de NF-e e no cadastro de compras")
        subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR_APAGADO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        cab_layout.addWidget(titulo)
        cab_layout.addWidget(subtitulo)

        raiz.addWidget(cabecalho)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        corpo_widget = QWidget()
        corpo_widget.setStyleSheet("background:transparent;")

        corpo = QVBoxLayout(corpo_widget)
        corpo.setContentsMargins(24, 20, 24, 20)
        corpo.setSpacing(14)

        self.razao_social = self._campo(corpo, "RAZÃO SOCIAL", "Nome Ltda")
        self.nome_fantasia = self._campo(corpo, "NOME FANTASIA", "Nome Fantasia")
        self.cnpj = self._campo(
            corpo, "CNPJ", "00.000.000/0000-00", cls=CpfCnpjField
        )
        self.telefone = self._campo(
            corpo, "TELEFONE", "(00) 00000-0000", cls=PhoneField
        )
        self.email = self._campo(
            corpo, "E-MAIL", "email@exemplo.com", cls=EmailField
        )
        self.cidade = self._campo(corpo, "CIDADE", "Cidade")
        self.estado = self._campo(corpo, "ESTADO (UF)", "Ex.: SP")

        lbl_margem = QLabel("MARGEM PADRÃO DE VENDA (%)")
        lbl_margem.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.margem_padrao = QDoubleSpinBox()
        self.margem_padrao.setRange(0, 999)
        self.margem_padrao.setDecimals(2)
        self.margem_padrao.setSuffix(" %")
        self.margem_padrao.setMinimumHeight(44)
        self.margem_padrao.setStyleSheet(f"""
            QDoubleSpinBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
        """)

        corpo.addWidget(lbl_margem)
        corpo.addWidget(self.margem_padrao)
        corpo.addStretch()

        scroll.setWidget(corpo_widget)
        raiz.addWidget(scroll, stretch=1)

        rodape = QHBoxLayout()
        rodape.setContentsMargins(24, 16, 24, 20)

        self.bt_cancelar = BotaoSecundario("Cancelar")
        self.bt_cancelar.clicked.connect(self.reject)

        self.bt_salvar = BotaoPrimario("Salvar")
        self.bt_salvar.clicked.connect(self.salvar)

        rodape.addWidget(self.bt_cancelar)
        rodape.addStretch()
        rodape.addWidget(self.bt_salvar)

        raiz.addLayout(rodape)

        if fornecedor:
            self.razao_social.setText(fornecedor.get("razao_social", ""))
            self.nome_fantasia.setText(fornecedor.get("nome_fantasia") or "")
            self.cnpj.setText(fornecedor.get("cnpj", ""))
            self.telefone.setText(fornecedor.get("telefone") or "")
            self.email.setText(fornecedor.get("email") or "")
            self.cidade.setText(fornecedor.get("cidade") or "")
            self.estado.setText(fornecedor.get("estado") or "")
            self.margem_padrao.setValue(float(fornecedor.get("margem_padrao") or 0))

    def _campo(self, layout, rotulo, placeholder, cls=None):
        from design.widgets import CampoTexto

        cls = cls or CampoTexto

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        campo = cls(placeholder)
        campo.setMinimumHeight(44)

        layout.addWidget(lbl)
        layout.addWidget(campo)

        return campo

    def salvar(self):

        razao_social = self.razao_social.text().strip()

        if not razao_social:
            QMessageBox.warning(self, "Atenção", "Informe a razão social.")
            return

        if not self.cnpj.valido:
            QMessageBox.warning(self, "Atenção", "Informe um CNPJ válido.")
            return

        if self.email.text().strip() and not email_valido(self.email.text()):
            QMessageBox.warning(self, "Atenção", "E-mail inválido.")
            return

        dados = {
            "razao_social": razao_social,
            "nome_fantasia": self.nome_fantasia.text().strip() or None,
            "cnpj": self.cnpj.text().strip(),
            "telefone": self.telefone.text().strip() or None,
            "email": self.email.text().strip() or None,
            "cidade": self.cidade.text().strip() or None,
            "estado": self.estado.text().strip() or None,
            "margem_padrao": self.margem_padrao.value(),
        }

        if self.fornecedor:
            dados["ativo"] = self.fornecedor.get("ativo", True)
            func, args = atualizar_fornecedor, (self.fornecedor["id"], dados)
        else:
            func, args = cadastrar_fornecedor, (dados,)

        self._definir_salvando(True)

        rodar_em_thread(
            self,
            func,
            *args,
            ao_sucesso=self._ao_salvar_sucesso,
            ao_erro=self._ao_salvar_erro,
            ao_finalizar=self._ao_salvar_finalizado,
        )

    def _definir_salvando(self, salvando: bool):
        self.bt_salvar.setEnabled(not salvando)
        self.bt_cancelar.setEnabled(not salvando)

    def _ao_salvar_sucesso(self, response):

        if response.status_code in (200, 201):
            self.fornecedor_salvo = response.json()
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_salvar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_salvar_finalizado(self):
        self._definir_salvando(False)
