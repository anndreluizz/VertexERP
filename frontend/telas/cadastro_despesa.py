import base64
import mimetypes
from datetime import date, datetime

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDateEdit,
    QComboBox,
    QPushButton,
    QFileDialog,
    QFrame,
    QWidget,
    QMessageBox,
)

from services.conta_pagar_service import (
    cadastrar_conta_pagar,
    atualizar_conta_pagar,
    remover_documento_conta_pagar,
)
from services.categoria_despesa_service import listar_categorias_despesa
from services.centro_custo_service import listar_centros_custo
from services.plano_conta_service import listar_planos_conta
from services.worker import rodar_em_thread
from telas.gerenciar_categorias_despesa import (
    GerenciarCategoriasDespesaDialog,
)
from telas.gerenciar_centros_custo import GerenciarCentrosCustoDialog
from telas.gerenciar_plano_contas import GerenciarPlanoContasDialog

from design import tokens
from design.widgets import (
    BotaoPerigo, BotaoSecundario, CampoTexto, DialogoPadrao, campo_rotulado,
    grade_formulario, titulo_secao,
)
from utils.formatacao import formatar_moeda


def _parse_valor(texto):
    try:
        return max(0.0, float(
            (texto or "").strip().replace(".", "").replace(",", ".") or 0
        ))
    except ValueError:
        return 0.0


class CadastroDespesaDialog(DialogoPadrao):
    """Nova / Editar despesa no molde padrão das subtelas: duas colunas
    agrupadas em Despesa / Classificação / Pagamento e documento (era
    uma coluna de 440px com rolagem comprida)."""

    def __init__(self, conta=None, duplicar_de=None, parent=None):

        editando = conta is not None

        super().__init__(
            "Editar Despesa" if editando else "Nova Despesa",
            "Contas e despesas do estabelecimento",
            "wallet", tokens.ALERTA, tokens.ALERTA_CLARO,
            largura=DialogoPadrao.GRANDE, parent=parent,
        )

        self.conta = conta

        # documento_bytes so fica preenchido quando o usuario escolhe um
        # arquivo NOVO nesta sessao do dialogo -- e o que decide se
        # salvar() manda documento_base64 pro backend (ver logica la
        # embaixo). Remover um documento ja existente acontece na hora,
        # direto pela API (ver remover_documento()), sem precisar de
        # nenhum estado aqui pra lembrar disso depois.
        self.documento_bytes = None
        self.documento_nome_arquivo = None
        self.documento_tipo_arquivo = None

        # ======================
        # DESPESA
        # ======================

        self.descricao = CampoTexto("Ex: aluguel, funcionária, luz...")
        self.valor = CampoTexto("0,00")
        self.valor.textChanged.connect(self._atualizar_valor_final)

        self.vencimento = QDateEdit()
        self.vencimento.setCalendarPopup(True)
        self.vencimento.setDisplayFormat("dd/MM/yyyy")
        self.vencimento.setDate(QDate.currentDate())
        self.vencimento.setMinimumHeight(44)
        self.vencimento.setStyleSheet(f"""
            QDateEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QDateEdit:focus {{ border-color: {tokens.PRIMARIA}; }}
        """)

        self.corpo.addWidget(titulo_secao("Despesa"))
        self.corpo.addLayout(grade_formulario(
            (campo_rotulado("Descrição *", self.descricao), 0, 0, 1, 2),
            (campo_rotulado("Valor (R$) *", self.valor), 1, 0),
            (campo_rotulado("Vencimento", self.vencimento), 1, 1),
        ))

        # ======================
        # CLASSIFICAÇÃO
        # ======================

        self.categoria = self._combo()
        self._carregar_categorias()
        self.centro_custo = self._combo()
        self._carregar_centros_custo()
        self.plano_conta = self._combo()
        self._carregar_planos_conta()

        grade_classificacao = grade_formulario(
            (self._combo_com_gerenciar("Categoria", self.categoria, self.gerenciar_categorias), 0, 0),
            (self._combo_com_gerenciar("Centro de custo", self.centro_custo, self.gerenciar_centros_custo), 0, 1),
            (self._combo_com_gerenciar("Plano de contas", self.plano_conta, self.gerenciar_plano_contas), 0, 2),
        )
        grade_classificacao.setColumnStretch(2, 1)

        self.corpo.addWidget(titulo_secao("Classificação"))
        self.corpo.addLayout(grade_classificacao)

        # ======================
        # PAGAMENTO E DOCUMENTO
        # ======================

        self.numero_boleto = CampoTexto("Bipe o boleto ou digite a linha digitável")
        self.observacoes = CampoTexto("Anotações internas sobre essa despesa")

        linha_anexo_widget = QWidget()
        linha_anexo_widget.setStyleSheet("background:transparent;")
        linha_anexo = QHBoxLayout(linha_anexo_widget)
        linha_anexo.setContentsMargins(0, 0, 0, 0)
        linha_anexo.setSpacing(8)

        self.bt_anexar = BotaoSecundario("Anexar boleto", icone_nome="file-text")
        self.bt_anexar.setAutoDefault(False)
        self.bt_anexar.clicked.connect(self.escolher_documento)

        self.lbl_arquivo_anexado = QLabel("Nenhum arquivo anexado")
        self.lbl_arquivo_anexado.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        self.lbl_arquivo_anexado.setWordWrap(True)

        self.bt_remover_anexo = QPushButton("Remover")
        self.bt_remover_anexo.setCursor(Qt.PointingHandCursor)
        self.bt_remover_anexo.setAutoDefault(False)
        self.bt_remover_anexo.setVisible(False)
        self.bt_remover_anexo.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.ERRO}; font-size:{tokens.TAMANHO_SM}px; font-weight:600;
            }}
        """)
        self.bt_remover_anexo.clicked.connect(self.remover_documento)

        linha_anexo.addWidget(self.bt_anexar)
        linha_anexo.addWidget(self.lbl_arquivo_anexado, stretch=1)
        linha_anexo.addWidget(self.bt_remover_anexo)

        self.corpo.addWidget(titulo_secao("Pagamento e documento"))
        self.corpo.addLayout(grade_formulario(
            (campo_rotulado("Código de barras (boleto)", self.numero_boleto), 0, 0),
            (campo_rotulado("Documento (PDF ou foto)", linha_anexo_widget), 0, 1),
            (campo_rotulado("Observações", self.observacoes), 1, 0, 1, 2),
        ))

        # ---- desconto / juros / multa (colapsável) ----

        self.bt_alternar_ajuste = QPushButton("+ Desconto, juros ou multa")
        self.bt_alternar_ajuste.setCursor(Qt.PointingHandCursor)
        self.bt_alternar_ajuste.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; text-align:left;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:600; padding: 4px 0;
            }}
        """)
        self.bt_alternar_ajuste.clicked.connect(self._alternar_bloco_ajuste)
        self.corpo.addWidget(self.bt_alternar_ajuste)

        self.bloco_ajuste = QFrame()
        self.bloco_ajuste.setVisible(False)
        self.bloco_ajuste.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
        """)

        ajuste_layout = QVBoxLayout(self.bloco_ajuste)
        ajuste_layout.setContentsMargins(14, 12, 14, 12)
        ajuste_layout.setSpacing(8)

        linha_ajuste = QHBoxLayout()
        linha_ajuste.setSpacing(10)

        self.desconto = self._campo_ajuste(linha_ajuste, "Desconto")
        self.juros = self._campo_ajuste(linha_ajuste, "Juros")
        self.multa = self._campo_ajuste(linha_ajuste, "Multa")

        ajuste_layout.addLayout(linha_ajuste)

        linha_final = QHBoxLayout()

        lbl_final_titulo = QLabel("Valor final (será salvo)")
        lbl_final_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)

        self.lbl_valor_final = QLabel("R$ 0,00")
        self.lbl_valor_final.setAlignment(Qt.AlignRight)
        self.lbl_valor_final.setStyleSheet(f"""
            background:transparent; color:{tokens.SECUNDARIA_HOVER};
            font-size:{tokens.TAMANHO_MD}px; font-weight:800;
        """)

        linha_final.addWidget(lbl_final_titulo)
        linha_final.addStretch()
        linha_final.addWidget(self.lbl_valor_final)

        ajuste_layout.addLayout(linha_final)

        self.corpo.addWidget(self.bloco_ajuste)
        self.corpo.addStretch()

        # ======================
        # RODAPÉ
        # ======================

        self.bt_salvar = BotaoPerigo(
            "Salvar Alterações" if editando else "Cadastrar Despesa",
            icone_nome="check",
        )
        self.bt_salvar.setAutoDefault(False)
        self.bt_salvar.clicked.connect(self.salvar)
        self.definir_botoes(self.bt_salvar)

        if editando:
            self._preencher(conta)
        elif duplicar_de:
            self._preencher(duplicar_de, duplicando=True)

        self._atualizar_valor_final()

        self.ajustar_altura()
        self.descricao.setFocus()

    def _combo(self):
        combo = QComboBox()
        combo.setMinimumHeight(44)
        combo.setCursor(Qt.PointingHandCursor)
        combo.setStyleSheet(f"""
            QComboBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QComboBox:focus {{ border-color: {tokens.PRIMARIA}; }}
        """)
        return combo

    def _combo_com_gerenciar(self, rotulo, combo, ao_gerenciar):
        """Rótulo + link "Gerenciar" na mesma linha, combo embaixo."""

        bloco = QWidget()
        bloco.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(bloco)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        cabecalho = QHBoxLayout()
        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; color:{tokens.TEXTO_SECUNDARIO};
        """)
        bt = QPushButton("Gerenciar")
        bt.setAutoDefault(False)
        bt.setCursor(Qt.PointingHandCursor)
        bt.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_XS}px; font-weight:700;
            }}
            QPushButton:hover {{ color:{tokens.PRIMARIA_HOVER}; }}
        """)
        bt.clicked.connect(ao_gerenciar)
        cabecalho.addWidget(lbl)
        cabecalho.addStretch()
        cabecalho.addWidget(bt)

        layout.addLayout(cabecalho)
        layout.addWidget(combo)
        return bloco

    # ======================================

    def _campo_ajuste(self, layout, rotulo):

        col = QVBoxLayout()
        col.setSpacing(4)

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; color:{tokens.TEXTO_SECUNDARIO};
        """)

        campo = CampoTexto("0,00")
        campo.textChanged.connect(self._atualizar_valor_final)

        col.addWidget(lbl)
        col.addWidget(campo)

        layout.addLayout(col)

        return campo

    def _alternar_bloco_ajuste(self):
        self.bloco_ajuste.setVisible(not self.bloco_ajuste.isVisible())

    def _atualizar_valor_final(self):

        valor_base = _parse_valor(self.valor.text())
        desconto = _parse_valor(self.desconto.text())
        juros = _parse_valor(self.juros.text())
        multa = _parse_valor(self.multa.text())

        final = max(0.0, valor_base - desconto + juros + multa)

        self.lbl_valor_final.setText(formatar_moeda(final))

        return final

    def _carregar_categorias(self):

        self._categoria_selecionada_pendente = self.categoria.currentText()

        rodar_em_thread(
            self,
            listar_categorias_despesa,
            ao_sucesso=self._ao_carregar_categorias_sucesso,
        )

    def _ao_carregar_categorias_sucesso(self, categorias):

        self.categoria.clear()

        nomes = [c["nome"] for c in categorias]
        self.categoria.addItems(nomes)

        selecionada = self._categoria_selecionada_pendente
        if selecionada and self.categoria.findText(selecionada) >= 0:
            self.categoria.setCurrentText(selecionada)

    def gerenciar_categorias(self):

        dialogo = GerenciarCategoriasDespesaDialog(parent=self)
        dialogo.exec()

        self._carregar_categorias()

    def _carregar_centros_custo(self):

        self._centro_custo_selecionado_pendente = (
            self.centro_custo.currentText()
        )

        rodar_em_thread(
            self,
            listar_centros_custo,
            ao_sucesso=self._ao_carregar_centros_custo_sucesso,
        )

    def _ao_carregar_centros_custo_sucesso(self, centros):

        self.centro_custo.clear()
        self.centro_custo.addItem("Nenhum")

        nomes = [c["nome"] for c in centros]
        self.centro_custo.addItems(nomes)

        selecionado = self._centro_custo_selecionado_pendente
        if selecionado and self.centro_custo.findText(selecionado) >= 0:
            self.centro_custo.setCurrentText(selecionado)

    def gerenciar_centros_custo(self):

        dialogo = GerenciarCentrosCustoDialog(parent=self)
        dialogo.exec()

        self._carregar_centros_custo()

    def _carregar_planos_conta(self):

        self._plano_conta_selecionado_pendente = (
            self.plano_conta.currentData()
        )

        rodar_em_thread(
            self,
            listar_planos_conta,
            ao_sucesso=self._ao_carregar_planos_conta_sucesso,
        )

    def _ao_carregar_planos_conta_sucesso(self, contas):

        self.plano_conta.clear()
        self.plano_conta.addItem("Nenhum", None)

        por_id = {c["id"]: c for c in contas}

        def caminho(conta):
            partes = [conta["nome"]]
            pai_id = conta.get("conta_pai_id")
            while pai_id in por_id:
                pai = por_id[pai_id]
                partes.insert(0, pai["nome"])
                pai_id = pai.get("conta_pai_id")
            return " > ".join(partes)

        despesas = sorted(
            (c for c in contas if c["tipo"] == "DESPESA"),
            key=caminho,
        )

        for conta in despesas:
            self.plano_conta.addItem(caminho(conta), conta["id"])

        selecionado = self._plano_conta_selecionado_pendente
        if selecionado is not None:
            indice = self.plano_conta.findData(selecionado)
            if indice >= 0:
                self.plano_conta.setCurrentIndex(indice)

    def gerenciar_plano_contas(self):

        dialogo = GerenciarPlanoContasDialog(parent=self)
        dialogo.exec()

        self._carregar_planos_conta()

    # limite pra nao mandar um JSON gigante num POST so' -- um boleto/
    # nota legivel nunca passa disso; sem esse limite, uma foto de
    # celular (5-15MB, ~33% maior em base64) pode derrubar o backend
    # por falta de memoria numa maquina de loja mais simples
    _TAMANHO_MAX_DOCUMENTO = 8 * 1024 * 1024

    def escolher_documento(self):

        caminho, _ = QFileDialog.getOpenFileName(
            self, "Anexar Boleto", "",
            "Documentos (*.pdf *.jpg *.jpeg *.png)",
        )

        if not caminho:
            return

        with open(caminho, "rb") as arquivo:
            conteudo = arquivo.read()

        if len(conteudo) > self._TAMANHO_MAX_DOCUMENTO:
            QMessageBox.warning(
                self, "Arquivo muito grande",
                "Esse arquivo passa de 8 MB. Anexe um PDF do boleto "
                "ou uma foto mais leve (tire com menos resolução ou "
                "comprima antes).",
            )
            return

        self.documento_bytes = conteudo

        nome_arquivo = caminho.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        self.documento_nome_arquivo = nome_arquivo
        self.documento_tipo_arquivo = (
            mimetypes.guess_type(caminho)[0] or "application/octet-stream"
        )

        self.lbl_arquivo_anexado.setText(nome_arquivo)
        self.lbl_arquivo_anexado.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO};
        """)
        self.bt_remover_anexo.setVisible(True)

    def remover_documento(self):

        # arquivo so escolhido agora, ainda nao salvo -- so limpa local,
        # sem precisar chamar a API (nada foi persistido ainda)
        if self.documento_bytes:
            self.documento_bytes = None
            self.documento_nome_arquivo = None
            self.documento_tipo_arquivo = None
            self.lbl_arquivo_anexado.setText("Nenhum arquivo anexado")
            self.lbl_arquivo_anexado.setStyleSheet(f"""
                background:transparent; font-size:{tokens.TAMANHO_SM}px;
                color:{tokens.TEXTO_TERCIARIO};
            """)
            self.bt_remover_anexo.setVisible(False)
            return

        # documento que ja estava salvo -- remove de verdade, na hora
        # (mesmo criterio de outras acoes imediatas do app, sem rascunho)
        if self.conta and self.conta.get("tem_documento"):
            self.bt_remover_anexo.setEnabled(False)
            rodar_em_thread(
                self,
                remover_documento_conta_pagar,
                self.conta["id"],
                ao_sucesso=self._ao_remover_documento_sucesso,
                ao_erro=self._ao_remover_documento_erro,
                ao_finalizar=self._ao_remover_documento_finalizado,
            )

    def _ao_remover_documento_sucesso(self, resposta):

        if resposta.status_code != 200:
            QMessageBox.critical(
                self, "Erro", "Não foi possível remover o documento."
            )
            return

        self.lbl_arquivo_anexado.setText("Nenhum arquivo anexado")
        self.lbl_arquivo_anexado.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        self.bt_remover_anexo.setVisible(False)

    def _ao_remover_documento_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível remover o documento.\n{erro}"
        )

    def _ao_remover_documento_finalizado(self):
        self.bt_remover_anexo.setEnabled(True)

    def _preencher(self, conta, duplicando=False):

        self.descricao.setText(conta.get("descricao") or "")
        categoria = conta.get("categoria")
        if categoria and self.categoria.findText(categoria) >= 0:
            self.categoria.setCurrentText(categoria)

        centro_custo = conta.get("centro_custo")
        if centro_custo and self.centro_custo.findText(centro_custo) >= 0:
            self.centro_custo.setCurrentText(centro_custo)

        plano_conta_id = conta.get("plano_conta_id")
        if plano_conta_id is not None:
            indice = self.plano_conta.findData(plano_conta_id)
            if indice >= 0:
                self.plano_conta.setCurrentIndex(indice)

        if not duplicando:
            self.numero_boleto.setText(conta.get("numero_boleto") or "")
            self.observacoes.setText(conta.get("observacao") or "")

            if conta.get("tem_documento"):
                self.lbl_arquivo_anexado.setText(
                    conta.get("documento_nome") or "Documento anexado"
                )
                self.lbl_arquivo_anexado.setStyleSheet(f"""
                    background:transparent; font-size:{tokens.TAMANHO_SM}px;
                    color:{tokens.TEXTO};
                """)
                self.bt_remover_anexo.setVisible(True)

        valor = conta.get("valor", 0)
        self.valor.setText(
            f"{float(valor):.2f}".replace(".", ",")
        )

        vencimento = conta.get("data_vencimento", "")
        try:
            data = datetime.fromisoformat(vencimento).date()
            self.vencimento.setDate(
                QDate(data.year, data.month, data.day)
            )
        except (ValueError, TypeError):
            pass

    # ======================================

    def salvar(self):

        descricao = self.descricao.text().strip()

        if not descricao:
            QMessageBox.warning(
                self,
                "Atenção",
                "Informe a descrição da despesa.",
            )
            return

        valor = self._atualizar_valor_final()

        if valor <= 0:
            QMessageBox.warning(
                self,
                "Atenção",
                "Informe um valor válido pra despesa.",
            )
            return

        data_qt = self.vencimento.date()
        data_vencimento = date(
            data_qt.year(), data_qt.month(), data_qt.day()
        ).isoformat() + "T00:00:00"

        centro_custo_texto = self.centro_custo.currentText()

        dados = {
            "descricao": descricao,
            "categoria": self.categoria.currentText(),
            "centro_custo": (
                None if centro_custo_texto in ("", "Nenhum")
                else centro_custo_texto
            ),
            "plano_conta_id": self.plano_conta.currentData(),
            "valor": valor,
            "data_vencimento": data_vencimento,
            "numero_boleto": self.numero_boleto.text().strip() or None,
            "observacao": self.observacoes.text().strip() or None,
        }

        # so manda o documento se um arquivo NOVO foi escolhido nesta
        # sessao do dialogo -- se nao mandar nada, o backend mantem o
        # que ja estava anexado (ver ContaPagarService.atualizar). A
        # remocao de um documento existente ja aconteceu na hora, em
        # remover_documento(), nao precisa repetir aqui.
        if self.documento_bytes:
            dados["documento_base64"] = base64.b64encode(
                self.documento_bytes
            ).decode("ascii")
            dados["documento_nome"] = self.documento_nome_arquivo
            dados["documento_tipo"] = self.documento_tipo_arquivo

        if self.conta:
            func, args = atualizar_conta_pagar, (self.conta["id"], dados)
        else:
            func, args = cadastrar_conta_pagar, (dados,)

        self.bt_salvar.setEnabled(False)

        rodar_em_thread(
            self,
            func,
            *args,
            ao_sucesso=self._ao_salvar_sucesso,
            ao_erro=self._ao_salvar_erro,
            ao_finalizar=self._ao_salvar_finalizado,
        )

    def _ao_salvar_sucesso(self, response):

        if response.status_code in (200, 201):

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
        self.bt_salvar.setEnabled(True)
