import base64

from utils.maiusculas import forcar_maiusculas
from PySide6.QtCore import Qt, QDate, QBuffer, QIODevice
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDateEdit,
    QCheckBox,
    QPushButton,
    QWidget,
    QFileDialog,
    QMessageBox,
)

from design import tokens
from design.icons import icone
from design.widgets import (
    BotaoPrimario, CampoTexto, DialogoPadrao, campo_rotulado, grade_formulario,
    titulo_secao,
)
from services.cliente_service import (
    cadastrar_cliente,
    atualizar_cliente,
    obter_foto_cliente,
)
from services.worker import rodar_em_thread
from utils.validacao import email_valido
from widgets.fields.cpf_field import CpfCnpjField
from widgets.fields.phone_field import PhoneField
from widgets.fields.email_field import EmailField


def _parse_valor_opcional(texto):

    texto = (texto or "").strip()

    if not texto:
        return None

    try:
        return max(0.0, float(texto.replace(".", "").replace(",", ".")))
    except ValueError:
        return None


_TAMANHO_FOTO = 96


def _foto_redonda(pixmap, lado=_TAMANHO_FOTO):
    """Foto cortada em círculo (antes era só escalada num quadrado -- o
    border-radius do QLabel não recorta o pixmap)."""

    pixmap = pixmap.scaled(lado, lado, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    resultado = QPixmap(lado, lado)
    resultado.fill(Qt.transparent)
    pintor = QPainter(resultado)
    pintor.setRenderHint(QPainter.Antialiasing)
    caminho = QPainterPath()
    caminho.addEllipse(0, 0, lado, lado)
    pintor.setClipPath(caminho)
    pintor.drawPixmap((lado - pixmap.width()) // 2, (lado - pixmap.height()) // 2, pixmap)
    pintor.end()
    return resultado


class CadastroClienteDialog(DialogoPadrao):
    """Novo cliente e Editar cliente usam a mesma tela: formulário em
    duas colunas agrupado em Dados pessoais e contato / Endereço /
    Fiado, com a foto ao lado do nome."""

    def __init__(self, cliente=None, parent=None):

        editando = cliente is not None

        super().__init__(
            "Editar Cliente" if editando else "Novo Cliente",
            "Atualize os dados do cliente" if editando
            else "Cadastre o cliente pra liberar o fiado dele",
            "user",
            largura=DialogoPadrao.GRANDE,
            parent=parent,
        )

        self.cliente = cliente
        self.cliente_salvo = None
        self.foto_bytes = None
        self._tem_foto_salva = False

        # ======================
        # FOTO + DADOS PESSOAIS
        # ======================

        topo = QHBoxLayout()
        topo.setSpacing(24)

        col_foto = QVBoxLayout()
        col_foto.setSpacing(6)
        col_foto.setAlignment(Qt.AlignTop)

        self.lbl_avatar = QLabel()
        self.lbl_avatar.setFixedSize(_TAMANHO_FOTO, _TAMANHO_FOTO)
        self.lbl_avatar.setAlignment(Qt.AlignCenter)

        bt_foto = QPushButton("Alterar foto")
        bt_foto.setCursor(Qt.PointingHandCursor)
        bt_foto.setAutoDefault(False)
        bt_foto.setIcon(icone("edit-2", cor=tokens.PRIMARIA, tamanho=13))
        bt_foto.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; border-radius:6px;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:600; padding:4px 8px;
            }}
            QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA}; }}
        """)
        bt_foto.clicked.connect(self.escolher_foto)

        col_foto.addSpacing(26)
        col_foto.addWidget(self.lbl_avatar, 0, Qt.AlignHCenter)
        col_foto.addWidget(bt_foto, 0, Qt.AlignHCenter)

        self.nome = CampoTexto("Nome completo")
        self.cpf = CpfCnpjField("000.000.000-00")

        self.data_nascimento = QDateEdit()
        self.data_nascimento.setCalendarPopup(True)
        self.data_nascimento.setDisplayFormat("dd/MM/yyyy")
        self.data_nascimento.setDate(QDate(2000, 1, 1))
        self.data_nascimento.setMinimumHeight(44)
        self.data_nascimento.setEnabled(False)
        self.data_nascimento.setStyleSheet(f"""
            QDateEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QDateEdit:focus {{ border-color: {tokens.PRIMARIA}; }}
            QDateEdit:disabled {{ background: {tokens.FUNDO}; color: {tokens.TEXTO_TERCIARIO}; }}
        """)

        self.chk_sem_nascimento = QCheckBox("Não informar")
        self.chk_sem_nascimento.setChecked(True)
        self.chk_sem_nascimento.toggled.connect(
            lambda marcado: self.data_nascimento.setEnabled(not marcado)
        )

        linha_nascimento = QWidget()
        linha_nascimento.setStyleSheet("background:transparent;")
        layout_nascimento = QHBoxLayout(linha_nascimento)
        layout_nascimento.setContentsMargins(0, 0, 0, 0)
        layout_nascimento.setSpacing(10)
        layout_nascimento.addWidget(self.data_nascimento, stretch=1)
        layout_nascimento.addWidget(self.chk_sem_nascimento)

        # contato junto dos dados pessoais, ao lado da foto -- uma seção
        # a menos e o formulário inteiro cabe sem rolar em 1366x768
        self.whatsapp = PhoneField("(00) 00000-0000")
        self.email = EmailField("email@exemplo.com")

        col_pessoal = QVBoxLayout()
        col_pessoal.setSpacing(14)
        col_pessoal.addWidget(titulo_secao("Dados pessoais e contato"))
        col_pessoal.addLayout(grade_formulario(
            (campo_rotulado("Nome *", self.nome), 0, 0, 1, 2),
            (campo_rotulado("CPF/CNPJ", self.cpf), 1, 0),
            (campo_rotulado("Data de nascimento", linha_nascimento), 1, 1),
            (campo_rotulado("WhatsApp", self.whatsapp), 2, 0),
            (campo_rotulado("E-mail", self.email), 2, 1),
        ))

        topo.addLayout(col_foto)
        topo.addLayout(col_pessoal, stretch=1)
        self.corpo.addLayout(topo)

        # ======================
        # ENDEREÇO
        # ======================

        self.endereco = CampoTexto("Rua, número, bairro")
        self.cidade = CampoTexto("Cidade")
        self.estado = CampoTexto("UF")
        self.estado.setMaxLength(2)

        # uma linha só (rua larga, cidade, UF estreito) -- com duas, o
        # bloco do Fiado ficava abaixo da dobra numa tela 1366x768
        grade_endereco = grade_formulario(
            (campo_rotulado("Endereço", self.endereco), 0, 0),
            (campo_rotulado("Cidade", self.cidade), 0, 1),
            (campo_rotulado("UF", self.estado), 0, 2),
        )
        grade_endereco.setColumnStretch(0, 3)
        grade_endereco.setColumnStretch(1, 2)
        self.estado.setFixedWidth(80)

        self.corpo.addWidget(titulo_secao("Endereço"))
        self.corpo.addLayout(grade_endereco)

        # cadastro em MAIUSCULAS -- e-mail/CPF/telefone ficam de fora
        forcar_maiusculas(self.nome, self.endereco, self.cidade, self.estado)

        # ======================
        # FIADO
        # ======================

        self.limite_credito = CampoTexto("Ex.: 200,00")

        # reativar um cliente desativado só era possível direto no banco
        # -- agora o próprio Editar tem a opção
        self.chk_ativo = QCheckBox("Cliente ativo")
        self.chk_ativo.setChecked(True)

        itens_fiado = [(campo_rotulado(
            "Limite de crédito (R$)", self.limite_credito,
            "Em branco = sem limite. Passando do limite o sistema só "
            "avisa, não bloqueia a venda.",
        ), 0, 0)]

        if editando:
            itens_fiado.append((campo_rotulado(
                "Situação", self.chk_ativo,
                "Desmarque pra tirar o cliente das listas sem apagar o histórico.",
            ), 0, 1, Qt.AlignTop))

        self.corpo.addWidget(titulo_secao("Fiado"))
        self.corpo.addLayout(grade_formulario(*itens_fiado))

        self.corpo.addStretch()

        # ======================
        # RODAPÉ
        # ======================

        self.bt_salvar = BotaoPrimario(
            "Salvar Alterações" if editando else "Cadastrar Cliente",
            icone_nome="check",
        )
        self.bt_salvar.setAutoDefault(False)
        self.bt_salvar.clicked.connect(self.salvar)
        self.bt_cancelar = self.definir_botoes(self.bt_salvar)

        self._exibir_avatar_padrao()

        if editando:
            self._preencher(cliente)

        # iniciais acompanham o nome digitado enquanto não houver foto
        self.nome.textChanged.connect(self._ao_mudar_nome)

        self.ajustar_altura()
        self.nome.setFocus()

    # ======================================

    def _ao_mudar_nome(self, _texto):
        if self.foto_bytes is None and not self._tem_foto_salva:
            self._exibir_avatar_padrao()

    def _exibir_avatar_padrao(self):

        partes = (self.nome.text() or "").split()
        iniciais = (
            (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()
            if partes else "?"
        )

        self.lbl_avatar.setPixmap(QPixmap())
        self.lbl_avatar.setText(iniciais)
        self.lbl_avatar.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA};
            border-radius:{_TAMANHO_FOTO // 2}px; font-size:30px; font-weight:800;
        """)

    def _exibir_foto(self, pixmap):
        self.lbl_avatar.setText("")
        self.lbl_avatar.setStyleSheet("background:transparent;")
        self.lbl_avatar.setPixmap(_foto_redonda(pixmap))

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

    def escolher_foto(self):

        caminho, _ = QFileDialog.getOpenFileName(
            self, "Escolher Foto", "", "Imagens (*.jpg *.jpeg *.png)"
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

        self.foto_bytes = imagem_comprimida

        pixmap = QPixmap()
        pixmap.loadFromData(self.foto_bytes)
        self._exibir_foto(pixmap)

    def _preencher(self, cliente):

        self.nome.setText(cliente.get("nome") or "")
        self.whatsapp.setText(cliente.get("telefone") or "")
        self.cpf.setText(cliente.get("cpf_cnpj") or "")
        self.email.setText(cliente.get("email") or "")
        self.endereco.setText(cliente.get("endereco") or "")
        self.cidade.setText(cliente.get("cidade") or "")
        self.estado.setText(cliente.get("estado") or "")
        self.chk_ativo.setChecked(cliente.get("ativo", True))
        self._exibir_avatar_padrao()

        if cliente.get("limite_credito") is not None:
            self.limite_credito.setText(
                f"{cliente['limite_credito']:.2f}".replace(".", ",")
            )

        data_nascimento = cliente.get("data_nascimento")

        if data_nascimento:
            self.chk_sem_nascimento.setChecked(False)
            self.data_nascimento.setDate(
                QDate.fromString(data_nascimento[:10], "yyyy-MM-dd")
            )

        if cliente.get("tem_foto"):

            foto_bytes = obter_foto_cliente(cliente["id"])

            if foto_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(foto_bytes)
                self._tem_foto_salva = True
                self._exibir_foto(pixmap)

    # ======================================

    def salvar(self):

        nome = self.nome.text().strip()

        if not nome:
            QMessageBox.warning(self, "Atenção", "Informe o nome do cliente.")
            self.nome.setFocus()
            return

        if not email_valido(self.email.text()):
            QMessageBox.warning(
                self, "Atenção", "Informe um e-mail válido (ex.: nome@exemplo.com)."
            )
            self.email.setFocus()
            return

        dados = {
            "nome": nome,
            "telefone": self.whatsapp.text().strip() or None,
            "cpf_cnpj": self.cpf.text().strip() or None,
            "email": self.email.text().strip() or None,
            "endereco": self.endereco.text().strip() or None,
            "cidade": self.cidade.text().strip() or None,
            "estado": self.estado.text().strip() or None,
            "limite_credito": _parse_valor_opcional(self.limite_credito.text()),
        }

        dados["data_nascimento"] = (
            None
            if self.chk_sem_nascimento.isChecked()
            else self.data_nascimento.date().toString("yyyy-MM-dd")
        )

        if self.foto_bytes:
            dados["foto_base64"] = base64.b64encode(self.foto_bytes).decode("ascii")

        if self.cliente:
            dados["ativo"] = self.chk_ativo.isChecked()
            func, args = atualizar_cliente, (self.cliente["id"], dados)
        else:
            func, args = cadastrar_cliente, (dados,)

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

            self.cliente_salvo = response.json()

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
