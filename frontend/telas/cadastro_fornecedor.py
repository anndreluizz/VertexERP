from utils.maiusculas import forcar_maiusculas
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QMessageBox,
)

from design import tokens
from design.widgets import (
    BotaoPrimario, CampoTexto, DialogoPadrao, campo_rotulado, grade_formulario,
    titulo_secao,
)
from services.fornecedor_service import cadastrar_fornecedor, atualizar_fornecedor
from services.worker import rodar_em_thread
from utils.validacao import email_valido
from widgets.fields.cpf_field import CpfCnpjField
from widgets.fields.phone_field import PhoneField
from widgets.fields.email_field import EmailField


class CadastroFornecedorDialog(DialogoPadrao):
    """Novo e Editar fornecedor -- mesmo molde do cadastro de cliente:
    duas colunas agrupadas em Empresa / Contato e endereço / Compras."""

    def __init__(self, fornecedor=None, parent=None):

        editando = fornecedor is not None

        super().__init__(
            "Editar Fornecedor" if editando else "Novo Fornecedor",
            "Usado na importação de NF-e e no cadastro de compras",
            "truck",
            largura=DialogoPadrao.GRANDE,
            parent=parent,
        )

        self.fornecedor = fornecedor
        self.fornecedor_salvo = None

        # ---- empresa ----

        self.razao_social = CampoTexto("Nome Ltda")
        self.nome_fantasia = CampoTexto("Como a loja chama o fornecedor")
        self.cnpj = CpfCnpjField("00.000.000/0000-00")

        self.corpo.addWidget(titulo_secao("Empresa"))
        self.corpo.addLayout(grade_formulario(
            (campo_rotulado("Razão social *", self.razao_social), 0, 0, 1, 2),
            (campo_rotulado("Nome fantasia", self.nome_fantasia), 1, 0),
            (campo_rotulado("CNPJ *", self.cnpj), 1, 1),
        ))

        # ---- contato e endereço ----

        self.telefone = PhoneField("(00) 00000-0000")
        self.email = EmailField("email@exemplo.com")
        self.cidade = CampoTexto("Cidade")
        self.estado = CampoTexto("UF")
        self.estado.setMaxLength(2)
        self.estado.setFixedWidth(80)

        grade_contato = grade_formulario(
            (campo_rotulado("Telefone", self.telefone), 0, 0),
            (campo_rotulado("E-mail", self.email), 0, 1, 1, 2),
            (campo_rotulado("Cidade", self.cidade), 1, 0, 1, 2),
            (campo_rotulado("UF", self.estado), 1, 2),
        )

        self.corpo.addWidget(titulo_secao("Contato e endereço"))
        self.corpo.addLayout(grade_contato)

        # cadastro em MAIUSCULAS -- e-mail/CPF/telefone ficam de fora
        forcar_maiusculas(self.razao_social, self.nome_fantasia, self.cidade, self.estado)

        # ---- compras ----

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
            QDoubleSpinBox:focus {{ border-color: {tokens.PRIMARIA}; }}
        """)

        # reativar um fornecedor excluído (soft-delete) não tinha como
        # pela tela -- agora o próprio Editar tem a opção
        self.chk_ativo = QCheckBox("Fornecedor ativo")
        self.chk_ativo.setChecked(True)

        itens_compras = [(campo_rotulado(
            "Margem padrão de venda", self.margem_padrao,
            "Sugerida no preço de venda dos produtos importados de NF-e.",
        ), 0, 0)]
        if editando:
            itens_compras.append((campo_rotulado(
                "Situação", self.chk_ativo,
                "Desmarque pra tirar o fornecedor das listas de compra e importação.",
            ), 0, 1))

        self.corpo.addWidget(titulo_secao("Compras"))
        self.corpo.addLayout(grade_formulario(*itens_compras))
        self.corpo.addStretch()

        # ---- rodapé ----

        self.bt_salvar = BotaoPrimario(
            "Salvar Alterações" if editando else "Cadastrar Fornecedor",
            icone_nome="check",
        )
        self.bt_salvar.setAutoDefault(False)
        self.bt_salvar.clicked.connect(self.salvar)
        self.bt_cancelar = self.definir_botoes(self.bt_salvar)

        if fornecedor:
            self.razao_social.setText(fornecedor.get("razao_social", ""))
            self.nome_fantasia.setText(fornecedor.get("nome_fantasia") or "")
            self.cnpj.setText(fornecedor.get("cnpj", ""))
            self.telefone.setText(fornecedor.get("telefone") or "")
            self.email.setText(fornecedor.get("email") or "")
            self.cidade.setText(fornecedor.get("cidade") or "")
            self.estado.setText(fornecedor.get("estado") or "")
            self.margem_padrao.setValue(float(fornecedor.get("margem_padrao") or 0))
            self.chk_ativo.setChecked(fornecedor.get("ativo", True))

        self.ajustar_altura()
        self.razao_social.setFocus()

    def salvar(self):

        razao_social = self.razao_social.text().strip()

        if not razao_social:
            QMessageBox.warning(self, "Atenção", "Informe a razão social.")
            self.razao_social.setFocus()
            return

        if not self.cnpj.valido:
            QMessageBox.warning(self, "Atenção", "Informe um CNPJ válido.")
            self.cnpj.setFocus()
            return

        if self.email.text().strip() and not email_valido(self.email.text()):
            QMessageBox.warning(self, "Atenção", "E-mail inválido.")
            self.email.setFocus()
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
            dados["ativo"] = self.chk_ativo.isChecked()
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
