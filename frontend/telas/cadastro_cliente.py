import base64

from utils.maiusculas import forcar_maiusculas
from PySide6.QtCore import Qt, QDate, QBuffer, QIODevice
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDateEdit,
    QCheckBox,
    QFrame,
    QScrollArea,
    QWidget,
    QFileDialog,
    QMessageBox,
)

from design import tokens
from design.widgets import CampoTexto, BotaoPrimario, BotaoSecundario
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


class CadastroClienteDialog(QDialog):

    def __init__(self, cliente=None, parent=None):

        super().__init__(parent)

        self.cliente = cliente
        self.cliente_salvo = None
        self.foto_bytes = None

        editando = cliente is not None

        self.setWindowTitle("Editar Cliente" if editando else "Novo Cliente")
        self.setFixedWidth(460)
        self.resize(460, 740)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QFrame()
        cabecalho.setStyleSheet(f"background:{tokens.SIDEBAR};")

        cab_layout = QVBoxLayout(cabecalho)
        cab_layout.setContentsMargins(24, 20, 24, 20)
        cab_layout.setSpacing(2)

        titulo = QLabel("EDITAR CLIENTE" if editando else "+ NOVO CLIENTE")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_CLARO};
            font-size:{tokens.TAMANHO_LG}px; font-weight:800;
        """)

        subtitulo = QLabel(
            "Atualize os dados do cliente"
            if editando
            else "Cadastre o cliente pra liberar o fiado dele"
        )
        subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR_APAGADO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        cab_layout.addWidget(titulo)
        cab_layout.addWidget(subtitulo)

        raiz.addWidget(cabecalho)

        # ======================
        # CORPO (rolável)
        # ======================

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        corpo_widget = QWidget()
        corpo_widget.setStyleSheet("background:transparent;")

        corpo = QVBoxLayout(corpo_widget)
        corpo.setContentsMargins(24, 20, 24, 20)
        corpo.setSpacing(14)

        # ---- foto ----

        linha_foto = QHBoxLayout()
        linha_foto.setSpacing(14)

        self.lbl_avatar = QLabel()
        self.lbl_avatar.setFixedSize(64, 64)
        self.lbl_avatar.setAlignment(Qt.AlignCenter)
        self._exibir_avatar_padrao()

        bt_foto = BotaoSecundario("Alterar Foto")
        bt_foto.clicked.connect(self.escolher_foto)

        linha_foto.addWidget(self.lbl_avatar)
        linha_foto.addWidget(bt_foto)
        linha_foto.addStretch()

        corpo.addLayout(linha_foto)

        self.nome = self._campo(corpo, "NOME", "Nome completo")
        self.whatsapp = self._campo(
            corpo, "WHATSAPP", "(00) 00000-0000", cls=PhoneField
        )
        self.cpf = self._campo(
            corpo, "CPF/CNPJ", "000.000.000-00", cls=CpfCnpjField
        )
        self.email = self._campo(
            corpo, "E-MAIL", "email@exemplo.com", cls=EmailField
        )
        self.endereco = self._campo(corpo, "ENDEREÇO", "Rua, número, bairro")
        self.cidade = self._campo(corpo, "CIDADE", "Cidade")
        self.estado = self._campo(corpo, "ESTADO (UF)", "Ex.: SP")

        # cadastro em MAIUSCULAS -- e-mail/CPF/telefone ficam de fora
        forcar_maiusculas(self.nome, self.endereco, self.cidade, self.estado)

        # ---- data de nascimento (opcional) ----

        linha_nascimento = QHBoxLayout()
        linha_nascimento.setSpacing(10)

        col_nascimento = QVBoxLayout()
        col_nascimento.setSpacing(4)

        lbl_nascimento = QLabel("DATA DE NASCIMENTO")
        lbl_nascimento.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

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
            QDateEdit:disabled {{ background: {tokens.FUNDO}; color: {tokens.TEXTO_TERCIARIO}; }}
        """)

        col_nascimento.addWidget(lbl_nascimento)
        col_nascimento.addWidget(self.data_nascimento)

        self.chk_sem_nascimento = QCheckBox("Não informar")
        self.chk_sem_nascimento.setChecked(True)
        self.chk_sem_nascimento.toggled.connect(
            lambda marcado: self.data_nascimento.setEnabled(not marcado)
        )

        linha_nascimento.addLayout(col_nascimento, stretch=1)
        linha_nascimento.addWidget(self.chk_sem_nascimento, 0, Qt.AlignBottom)

        corpo.addLayout(linha_nascimento)

        self.limite_credito = self._campo(
            corpo, "LIMITE DE CRÉDITO NO FIADO (opcional)", "Ex.: 200,00"
        )

        dica_limite = QLabel(
            "Deixe em branco pra não definir limite. Ao ultrapassar, o "
            "sistema só avisa — não bloqueia a venda."
        )
        dica_limite.setWordWrap(True)
        dica_limite.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        corpo.addWidget(dica_limite)

        corpo.addStretch()

        scroll.setWidget(corpo_widget)
        raiz.addWidget(scroll, stretch=1)

        # ======================
        # RODAPÉ
        # ======================

        rodape = QFrame()
        rodape.setStyleSheet(f"""
            background:{tokens.CARD}; border-top:1px solid {tokens.BORDA};
        """)

        rodape_layout = QHBoxLayout(rodape)
        rodape_layout.setContentsMargins(24, 14, 24, 14)
        rodape_layout.setSpacing(10)

        self.bt_cancelar = BotaoSecundario("Cancelar")
        self.bt_cancelar.clicked.connect(self.reject)

        self.bt_salvar = BotaoPrimario(
            "Salvar Alterações" if editando else "Cadastrar Cliente"
        )
        self.bt_salvar.clicked.connect(self.salvar)

        rodape_layout.addWidget(self.bt_cancelar)
        rodape_layout.addWidget(self.bt_salvar)

        raiz.addWidget(rodape)

        if editando:
            self._preencher(cliente)

        self.nome.setFocus()

    # ======================================

    def _campo(self, layout, rotulo, placeholder, cls=CampoTexto):

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

    def _exibir_avatar_padrao(self):

        nome = (self.cliente or {}).get("nome") if self.cliente else ""
        iniciais = "".join(p[0] for p in (nome or "?").split()[:2]).upper() or "?"

        self.lbl_avatar.setPixmap(QPixmap())
        self.lbl_avatar.setText(iniciais)
        self.lbl_avatar.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA};
            border-radius:32px; font-size:20px; font-weight:800;
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

        self.lbl_avatar.setStyleSheet("background:transparent; border-radius:32px;")
        self.lbl_avatar.setPixmap(
            pixmap.scaled(
                64, 64, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
        )

    def _preencher(self, cliente):

        self.nome.setText(cliente.get("nome") or "")
        self.whatsapp.setText(cliente.get("telefone") or "")
        self.cpf.setText(cliente.get("cpf_cnpj") or "")
        self.email.setText(cliente.get("email") or "")
        self.endereco.setText(cliente.get("endereco") or "")
        self.cidade.setText(cliente.get("cidade") or "")
        self.estado.setText(cliente.get("estado") or "")

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
                self.lbl_avatar.setStyleSheet(
                    "background:transparent; border-radius:32px;"
                )
                self.lbl_avatar.setPixmap(
                    pixmap.scaled(
                        64, 64, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                    )
                )

    # ======================================

    def salvar(self):

        nome = self.nome.text().strip()

        if not nome:
            QMessageBox.warning(self, "Atenção", "Informe o nome do cliente.")
            return

        if not email_valido(self.email.text()):
            QMessageBox.warning(
                self, "Atenção", "Informe um e-mail válido (ex.: nome@exemplo.com)."
            )
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
            dados["ativo"] = self.cliente.get("ativo", True)
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
