import base64
import mimetypes
import calendar
import re
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, QDate, QEvent, QTimer
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
    QSpinBox,
    QCheckBox,
    QGridLayout,
)

from services.conta_pagar_service import (
    cadastrar_conta_pagar,
    cadastrar_conta_fixa,
    cadastrar_conta_parcelada,
    ler_boleto,
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
from utils.pix import ler_pix


_ESTILO_DATA = f"""
    QDateEdit {{
        border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
        padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
        background: {tokens.CARD};
    }}
    QDateEdit:focus {{ border-color: {tokens.PRIMARIA}; }}
"""


def _somar_meses(data, meses):
    """Mesmo dia `meses` depois (no último dia do mês quando ele é
    mais curto) -- mesma regra do backend pras parcelas."""
    total = data.year * 12 + data.month - 1 + meses
    ano, mes = total // 12, total % 12 + 1
    return date(ano, mes, min(data.day, calendar.monthrange(ano, mes)[1]))


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
        # BOLETO -- começa por ele: bipar o código ou anexar o PDF já
        # preenche valor, vencimento e fornecedor (ver _ler_boleto)
        # ======================

        self.numero_boleto = CampoTexto("Bipe o código de barras ou cole a linha digitável")
        self.numero_boleto.textChanged.connect(self._codigo_mudou)
        # o leitor manda Enter depois do código: aqui ele lê o boleto em
        # vez de apertar o Salvar (ver eventFilter)
        self.numero_boleto.installEventFilter(self)

        self._timer_codigo = QTimer(self)
        self._timer_codigo.setSingleShot(True)
        self._timer_codigo.setInterval(350)
        self._timer_codigo.timeout.connect(self._ler_codigo_digitado)
        self._codigo_lido = None
        self._beneficiario_cnpj = None

        linha_anexo_widget = QWidget()
        linha_anexo_widget.setStyleSheet("background:transparent;")
        linha_anexo = QHBoxLayout(linha_anexo_widget)
        linha_anexo.setContentsMargins(0, 0, 0, 0)
        linha_anexo.setSpacing(8)

        self.bt_anexar = BotaoSecundario("Anexar PDF ou foto", icone_nome="file-text")
        self.bt_anexar.setAutoDefault(False)
        self.bt_anexar.setToolTip("PDF do boleto: o sistema lê fornecedor, valor e vencimento")
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

        # faixa com o resultado da leitura (ok / aviso / erro)
        self.lbl_boleto = QLabel()
        self.lbl_boleto.setWordWrap(True)
        self.lbl_boleto.setVisible(False)

        self.corpo.addWidget(titulo_secao("Boleto"))
        self.corpo.addLayout(grade_formulario(
            (campo_rotulado("Código de barras", self.numero_boleto), 0, 0),
            (campo_rotulado("Documento (PDF ou foto)", linha_anexo_widget), 0, 1),
        ))
        self.corpo.addWidget(self.lbl_boleto)

        # ======================
        # PIX -- conta paga no Pix: a chave do fornecedor ou o copia e
        # cola que ele mandou (ver utils/pix.py)
        # ======================

        self.pix = CampoTexto("Cole a chave Pix (CPF/CNPJ, telefone, e-mail) ou o Pix copia e cola")
        self.pix.textChanged.connect(self._pix_mudou)

        self.lbl_pix = QLabel()
        self.lbl_pix.setWordWrap(True)
        self.lbl_pix.setVisible(False)

        self.corpo.addWidget(titulo_secao("Pix"))
        self.corpo.addLayout(grade_formulario(
            (campo_rotulado("Chave Pix ou copia e cola", self.pix), 0, 0, 1, 2),
        ))
        self.corpo.addWidget(self.lbl_pix)

        # ======================
        # DESPESA
        # ======================

        self.descricao = CampoTexto("Fornecedor ou o que é a conta (ex.: ADRIANA, luz, funcionária)")
        self.valor = CampoTexto("0,00")
        self.valor.textChanged.connect(self._atualizar_valor_final)

        self.vencimento = QDateEdit()
        self.vencimento.setCalendarPopup(True)
        self.vencimento.setDisplayFormat("dd/MM/yyyy")
        self.vencimento.setDate(QDate.currentDate())
        self.vencimento.setMinimumHeight(44)
        self.vencimento.setStyleSheet(_ESTILO_DATA)

        self.corpo.addWidget(titulo_secao("Despesa"))
        self.corpo.addLayout(grade_formulario(
            (campo_rotulado("Fornecedor / descrição *", self.descricao), 0, 0, 1, 2),
            (campo_rotulado("Valor (R$) *", self.valor), 1, 0),
            (campo_rotulado("Vencimento", self.vencimento), 1, 1),
        ))

        # ======================
        # REPETIÇÃO (só na despesa nova)
        # ======================

        self.repeticao = self._combo()
        self.repeticao.addItem("Só esta vez", "UNICA")
        self.repeticao.addItem("Parcelado (boletos)", "PARCELADO")
        self.repeticao.addItem("Todo mês (conta fixa)", "MENSAL")
        self.repeticao.currentIndexChanged.connect(self._atualizar_repeticao)

        self.parcelas = self._spin(2, 60, 3, " parcelas")
        self.parcelas.valueChanged.connect(self._repeticao_mudou)

        self.intervalo = self._combo()
        self.intervalo.addItem("Mesmo dia todo mês", "MENSAL")
        self.intervalo.addItem("A cada 30 dias", "30_DIAS")
        self.intervalo.currentIndexChanged.connect(self._repeticao_mudou)

        self.valor_variavel = QCheckBox("O valor muda todo mês (ex.: luz)")
        self.valor_variavel.setStyleSheet(f"""
            QCheckBox {{ background:transparent; color:{tokens.TEXTO};
                         font-size:{tokens.TAMANHO_SM}px; }}
        """)
        self.valor_variavel.toggled.connect(self._atualizar_repeticao)

        self.prazo = self._combo()
        self.prazo.addItem("Repete sempre", None)
        self.prazo.addItem("Por um número de meses", "MESES")
        self.prazo.currentIndexChanged.connect(self._atualizar_repeticao)
        self.meses = self._spin(1, 360, 12, " meses")
        self.meses.valueChanged.connect(self._atualizar_repeticao)

        self.lbl_repeticao = QLabel()
        self.lbl_repeticao.setWordWrap(True)
        self.lbl_repeticao.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA_HOVER};
            border-radius:{tokens.RADIUS_SM}px; padding:8px 12px;
            font-size:{tokens.TAMANHO_SM}px;
        """)

        # datas de cada parcela, editáveis (abre com "Ajustar datas")
        self.bt_ajustar_datas = QPushButton("Ajustar datas das parcelas")
        self.bt_ajustar_datas.setCursor(Qt.PointingHandCursor)
        self.bt_ajustar_datas.setAutoDefault(False)
        self.bt_ajustar_datas.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; text-align:left;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:600; padding: 2px 0;
            }}
        """)
        self.bt_ajustar_datas.clicked.connect(self._alternar_datas_parcelas)
        self.grade_datas = QGridLayout()
        self.grade_datas.setSpacing(8)
        self.bloco_datas = QWidget()
        self.bloco_datas.setStyleSheet("background:transparent;")
        self.bloco_datas.setLayout(self.grade_datas)
        self.bloco_datas.setVisible(False)
        self.datas_parcelas = []
        self._datas_editadas = False

        self.bloco_repeticao = QWidget()
        self.bloco_repeticao.setStyleSheet("background:transparent;")
        lay_rep = QVBoxLayout(self.bloco_repeticao)
        lay_rep.setContentsMargins(0, 0, 0, 0)
        lay_rep.setSpacing(8)
        linha_rep = QHBoxLayout()
        linha_rep.setSpacing(12)
        linha_rep.addWidget(self.repeticao, 2)
        linha_rep.addWidget(self.parcelas, 1)
        linha_rep.addWidget(self.intervalo, 2)
        linha_rep.addWidget(self.prazo, 2)
        linha_rep.addWidget(self.meses, 1)
        lay_rep.addLayout(linha_rep)
        lay_rep.addWidget(self.valor_variavel)
        lay_rep.addWidget(self.lbl_repeticao)
        lay_rep.addWidget(self.bt_ajustar_datas)
        lay_rep.addWidget(self.bloco_datas)

        self.titulo_repeticao = titulo_secao("Repetição")
        self.corpo.addWidget(self.titulo_repeticao)
        self.corpo.addWidget(self.bloco_repeticao)

        # editar uma conta mexe só nela -- repetir é só na despesa nova
        self.titulo_repeticao.setVisible(not editando)
        self.bloco_repeticao.setVisible(not editando)

        self.valor.textChanged.connect(self._atualizar_repeticao)
        self.vencimento.dateChanged.connect(self._repeticao_mudou)
        self._atualizar_repeticao()

        # ======================
        # CLASSIFICAÇÃO
        # ======================

        self.categoria = self._combo()
        # comeca VAZIA: antes ja vinha marcada a 1a da lista e passava
        # batido -- parcelas de fornecedor foram parar em "Energia"
        self.categoria.setPlaceholderText("Escolha a categoria")
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
        # OBSERVAÇÕES
        # ======================

        self.observacoes = CampoTexto("Anotações internas sobre essa despesa")

        self.corpo.addWidget(titulo_secao("Observações"))
        self.corpo.addLayout(grade_formulario(
            (campo_rotulado("Observações", self.observacoes), 0, 0, 1, 2),
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

    def _spin(self, minimo, maximo, valor, sufixo):
        spin = QSpinBox()
        spin.setRange(minimo, maximo)
        spin.setValue(valor)
        spin.setSuffix(sufixo)
        spin.setMinimumHeight(44)
        spin.setStyleSheet(f"""
            QSpinBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QSpinBox:focus {{ border-color: {tokens.PRIMARIA}; }}
        """)
        return spin

    # ======================================
    # LEITURA DO BOLETO
    # ======================================

    def eventFilter(self, obj, event):
        if (
            obj is self.numero_boleto
            and event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Return, Qt.Key_Enter)
        ):
            self._timer_codigo.stop()
            self._ler_codigo_digitado(avisar=True)
            return True
        return super().eventFilter(obj, event)

    def _codigo_mudou(self, texto):
        # leitor de código de barras "digita" rápido -- espera parar
        digitos = re.sub(r"\D", "", texto or "")
        if len(digitos) >= 44 and digitos != self._codigo_lido:
            self._timer_codigo.start()
        elif not digitos:
            self._mostrar_faixa_boleto(None)

    def _ler_codigo_digitado(self, avisar=False):
        digitos = re.sub(r"\D", "", self.numero_boleto.text())
        if not digitos or digitos == self._codigo_lido:
            return
        if len(digitos) not in (44, 47, 48):
            # leitor que corta ou repete números: avisa em vez de ficar quieto
            if avisar or len(digitos) > 48:
                self._mostrar_faixa_boleto(
                    f"O código tem {len(digitos)} números, mas o boleto tem 44 "
                    "(código de barras) ou 47/48 (linha digitável). Bipe de novo "
                    "ou digite a linha digitável.",
                    "erro",
                )
                # a próxima bipada substitui o pedaço lido
                self.numero_boleto.selectAll()
            return
        self._codigo_lido = digitos
        self._mostrar_faixa_boleto("Lendo o boleto...", "info")
        rodar_em_thread(
            self,
            ler_boleto,
            codigo=digitos,
            ao_sucesso=self._ao_ler_boleto,
            ao_erro=self._ao_ler_boleto_erro,
        )

    def _ler_pdf(self, conteudo):
        self._mostrar_faixa_boleto("Lendo o PDF do boleto...", "info")
        rodar_em_thread(
            self,
            ler_boleto,
            pdf_base64=base64.b64encode(conteudo).decode("ascii"),
            ao_sucesso=self._ao_ler_boleto,
            ao_erro=self._ao_ler_boleto_erro,
        )

    def _ao_ler_boleto(self, response):

        if response.status_code != 200:
            try:
                erro = response.json().get("detail") or response.text
            except Exception:
                erro = response.text
            self._mostrar_faixa_boleto(erro, "erro")
            return

        self._aplicar_boleto(response.json())

    def _ao_ler_boleto_erro(self, erro):
        self._mostrar_faixa_boleto(f"Não foi possível ler o boleto: {erro}", "erro")

    def _aplicar_boleto(self, dados):
        """Preenche a despesa com o que veio do boleto. Editando uma conta
        só mostra o resultado -- não troca nada do que já estava salvo."""

        novo = self.conta is None

        if dados.get("linha_digitavel"):
            self._codigo_lido = re.sub(r"\D", "", dados["linha_digitavel"])
            if re.sub(r"\D", "", self.numero_boleto.text()) != self._codigo_lido:
                self.numero_boleto.blockSignals(True)
                self.numero_boleto.setText(dados["linha_digitavel"])
                self.numero_boleto.blockSignals(False)
            self.numero_boleto.setCursorPosition(0)

        self._beneficiario_cnpj = dados.get("beneficiario_cnpj")

        if novo:
            if dados.get("valor") is not None:
                self.valor.setText(f"{float(dados['valor']):.2f}".replace(".", ","))
            if dados.get("vencimento"):
                venc = date.fromisoformat(dados["vencimento"])
                self.vencimento.setDate(QDate(venc.year, venc.month, venc.day))
            if dados.get("fornecedor_sugerido") and not self.descricao.text().strip():
                self.descricao.setText(dados["fornecedor_sugerido"])
            categoria = dados.get("categoria_sugerida")
            if categoria:
                self._categoria_selecionada_pendente = categoria
                if self.categoria.findText(categoria) >= 0:
                    self.categoria.setCurrentText(categoria)

        partes = []
        if dados.get("banco_nome"):
            partes.append(dados["banco_nome"])
        elif dados.get("segmento"):
            partes.append(dados["segmento"])
        if dados.get("fornecedor_sugerido"):
            partes.append(dados["fornecedor_sugerido"])
        if dados.get("valor") is not None:
            partes.append(formatar_moeda(float(dados["valor"])))
        if dados.get("vencimento"):
            partes.append("vence " + date.fromisoformat(dados["vencimento"]).strftime("%d/%m/%Y"))

        repetido = dados.get("ja_lancado")
        if repetido:
            situacao = {"PAGO": "já paga", "PENDENTE": "em aberto"}.get(
                repetido["status"], repetido["status"].lower()
            )
            self._mostrar_faixa_boleto(
                f"⚠ Esse boleto já foi lançado: {repetido.get('descricao') or 'Despesa'} "
                f"— {formatar_moeda(float(repetido['valor']))} ({situacao}). "
                "Confira antes de salvar para não pagar duas vezes.",
                "erro",
            )
        else:
            self._mostrar_faixa_boleto("✓ Boleto lido: " + " · ".join(partes), "sucesso")

        self._atualizar_valor_final()
        self._atualizar_repeticao()

        if novo and not repetido and dados.get("parcela_sugerida"):
            self._oferecer_parcela(dados)

    def _oferecer_parcela(self, dados):
        """Boleto de uma parcela já lançada (cada parcela tem o seu
        código): guarda o código nela em vez de criar outra despesa."""

        parcela = dados["parcela_sugerida"]
        venc_parcela = datetime.fromisoformat(parcela["data_vencimento"]).date()
        venc_boleto = date.fromisoformat(dados["vencimento"]) if dados.get("vencimento") else None

        texto = (
            f"Esse boleto é a parcela {parcela.get('parcela_numero')} de "
            f"{parcela.get('parcela_total')} de "
            f"{parcela.get('descricao') or 'Despesa'} "
            f"({formatar_moeda(float(parcela['valor']))}, vence "
            f"{venc_parcela.strftime('%d/%m/%Y')}).\n\n"
            "Guardar o código nessa parcela, em vez de lançar uma despesa nova?"
        )
        if venc_boleto and venc_boleto != venc_parcela:
            texto += f"\n\nO vencimento da parcela passa para {venc_boleto.strftime('%d/%m/%Y')}, como está no boleto."

        resposta = QMessageBox.question(
            self, "Parcela encontrada", texto,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if resposta != QMessageBox.Yes:
            return

        payload = {"numero_boleto": dados.get("linha_digitavel") or self.numero_boleto.text().strip()}
        if venc_boleto:
            payload["data_vencimento"] = f"{venc_boleto.isoformat()}T00:00:00"

        self.bt_salvar.setEnabled(False)
        rodar_em_thread(
            self,
            atualizar_conta_pagar,
            parcela["id"],
            payload,
            ao_sucesso=self._ao_salvar_sucesso,
            ao_erro=self._ao_salvar_erro,
            ao_finalizar=self._ao_salvar_finalizado,
        )

    def _pix_mudou(self, texto):
        """Mostra o que foi reconhecido. Copia e cola de uma despesa nova
        já preenche valor e fornecedor, se estiverem vazios."""

        lido = ler_pix(texto)

        if lido is None:
            self._mostrar_faixa(self.lbl_pix, None)
            return

        if lido["tipo"] == "chave":
            self._mostrar_faixa(self.lbl_pix, f"✓ {lido['tipo_chave']}: {lido['copiar']}", "sucesso")
            return

        self.pix.setCursorPosition(0)

        if self.conta is None:
            if lido["valor"] and _parse_valor(self.valor.text()) <= 0:
                self.valor.setText(f"{lido['valor']:.2f}".replace(".", ","))
            if lido["nome"] and not self.descricao.text().strip():
                self.descricao.setText(lido["nome"])

        partes = [p for p in (lido["nome"], lido["cidade"]) if p]
        if lido["valor"]:
            partes.append(formatar_moeda(lido["valor"]))
        self._mostrar_faixa(
            self.lbl_pix,
            "✓ Pix copia e cola" + (": " + " · ".join(partes) if partes else ""),
            "sucesso",
        )

    def _mostrar_faixa_boleto(self, texto, variante="info"):
        self._mostrar_faixa(self.lbl_boleto, texto, variante)

    def _mostrar_faixa(self, label, texto, variante="info"):

        if not texto:
            label.setVisible(False)
            self.ajustar_altura()
            return

        fundo, cor = {
            "sucesso": (tokens.SUCESSO_CLARO, tokens.SECUNDARIA_HOVER),
            "erro": (tokens.ERRO_CLARO, tokens.ERRO_HOVER),
            "info": (tokens.PRIMARIA_CLARA, tokens.PRIMARIA_HOVER),
        }[variante]
        label.setStyleSheet(f"""
            background:{fundo}; color:{cor};
            border-radius:{tokens.RADIUS_SM}px; padding:8px 12px;
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        label.setText(texto)
        label.setVisible(True)
        self.ajustar_altura()

    # ======================================
    # REPETIÇÃO
    # ======================================

    def _repeticao_mudou(self, *_):
        # quantidade/intervalo/1º vencimento mudou: as datas sugeridas
        # valem de novo (as que a pessoa tinha ajustado ficam pra trás)
        self._datas_editadas = False
        self._atualizar_repeticao()

    def _datas_sugeridas(self):
        data_qt = self.vencimento.date()
        primeiro = date(data_qt.year(), data_qt.month(), data_qt.day())
        n = self.parcelas.value()
        if self.intervalo.currentData() == "30_DIAS":
            return [primeiro + timedelta(days=30 * i) for i in range(n)]
        return [_somar_meses(primeiro, i) for i in range(n)]

    def _datas_das_parcelas(self):
        if self._datas_editadas and len(self.datas_parcelas) == self.parcelas.value():
            return [campo.date().toPython() for campo in self.datas_parcelas]
        return self._datas_sugeridas()

    def _alternar_datas_parcelas(self):
        self.bloco_datas.setVisible(not self.bloco_datas.isVisible())
        self._montar_datas_parcelas()
        self.ajustar_altura()

    def _montar_datas_parcelas(self):

        datas = self._datas_das_parcelas()

        while self.grade_datas.count():
            item = self.grade_datas.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.datas_parcelas = []

        for i, data in enumerate(datas):
            campo = QDateEdit()
            campo.setCalendarPopup(True)
            campo.setDisplayFormat("dd/MM/yyyy")
            campo.setDate(QDate(data.year, data.month, data.day))
            campo.setMinimumHeight(38)
            campo.setStyleSheet(_ESTILO_DATA)
            campo.dateChanged.connect(self._data_parcela_editada)
            rotulo = QLabel(f"{i + 1}ª")
            rotulo.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_SECUNDARIO};
                font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            """)
            linha, coluna = divmod(i, 4)
            self.grade_datas.addWidget(rotulo, linha, coluna * 2)
            self.grade_datas.addWidget(campo, linha, coluna * 2 + 1)
            self.datas_parcelas.append(campo)

    def _data_parcela_editada(self, *_):
        self._datas_editadas = True
        self._atualizar_repeticao(montar_datas=False)

    def _tipo_repeticao(self):
        if self.conta is not None:
            return "UNICA"
        return self.repeticao.currentData()

    def _atualizar_repeticao(self, *_, montar_datas=True):

        tipo = self.repeticao.currentData()
        parcelado = tipo == "PARCELADO"
        mensal = tipo == "MENSAL"

        self.parcelas.setVisible(parcelado)
        self.intervalo.setVisible(parcelado)
        self.bt_ajustar_datas.setVisible(parcelado)
        self.bloco_datas.setVisible(parcelado and self.bloco_datas.isVisible())
        self.valor_variavel.setVisible(mensal)
        self.prazo.setVisible(mensal)
        self.meses.setVisible(mensal and self.prazo.currentData() == "MESES")
        self.lbl_repeticao.setVisible(tipo != "UNICA")

        data_qt = self.vencimento.date()
        primeiro = date(data_qt.year(), data_qt.month(), data_qt.day())
        valor = _parse_valor(self.valor.text())

        if parcelado:
            n = self.parcelas.value()
            datas = [d.strftime("%d/%m") for d in self._datas_das_parcelas()]
            if n > 4:
                datas = datas[:3] + ["...", datas[-1]]
            self.lbl_repeticao.setText(
                f"Digite o valor de UMA parcela. Serão {n} contas de "
                f"{formatar_moeda(valor)} (total {formatar_moeda(valor * n)}), "
                f"vencendo {', '.join(datas)}."
            )
            if montar_datas and self.bloco_datas.isVisible():
                self._montar_datas_parcelas()
        elif mensal:
            if self.valor_variavel.isChecked():
                detalhe = (
                    "Todo mês a conta nasce com o valor do mês anterior marcada "
                    "\"Confirmar valor\"; quando a fatura chegar, você corrige."
                )
            else:
                detalhe = f"Todo mês a conta nasce com {formatar_moeda(valor)}."
            if self.prazo.currentData() == "MESES":
                ultimo = _somar_meses(primeiro, self.meses.value() - 1)
                fim = f" A última vence em {ultimo.strftime('%d/%m/%Y')} e depois para sozinha."
            else:
                fim = " Para parar, use Contas fixas na tela de Contas a Pagar."
            self.lbl_repeticao.setText(f"Vence todo dia {primeiro.day}. {detalhe}{fim}")

        if hasattr(self, "_corpo_widget"):
            self.ajustar_altura()

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
        else:
            self.categoria.setCurrentIndex(-1)

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

        if caminho.lower().endswith(".pdf"):
            self._ler_pdf(conteudo)

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

        # duplicar leva a chave Pix, mas nao o copia e cola (e de uma
        # cobranca so', como o boleto)
        pix = conta.get("pix")
        if pix and (not duplicando or (ler_pix(pix) or {}).get("tipo") == "chave"):
            self.pix.setText(pix)

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

        if self.categoria.currentIndex() < 0:
            QMessageBox.warning(
                self,
                "Atenção",
                "Escolha a categoria da despesa.",
            )
            self.categoria.setFocus()
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
            "pix": self.pix.text().strip() or None,
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

        if self._beneficiario_cnpj and not self.conta:
            dados["beneficiario_cnpj"] = self._beneficiario_cnpj

        tipo = self._tipo_repeticao()

        if self.conta:
            func, args = atualizar_conta_pagar, (self.conta["id"], dados)
        elif tipo == "PARCELADO":
            dados["intervalo"] = self.intervalo.currentData()
            if self._datas_editadas:
                dados["vencimentos"] = [d.isoformat() for d in self._datas_das_parcelas()]
            func, args = cadastrar_conta_parcelada, (dados, self.parcelas.value())
        elif tipo == "MENSAL":
            func, args = cadastrar_conta_fixa, ({
                "descricao": descricao,
                "valor": valor,
                "primeiro_vencimento": data_vencimento[:10],
                "valor_variavel": self.valor_variavel.isChecked(),
                "categoria": dados["categoria"],
                "centro_custo": dados["centro_custo"],
                "plano_conta_id": dados["plano_conta_id"],
                "observacao": dados["observacao"],
                "meses": self.meses.value() if self.prazo.currentData() == "MESES" else None,
                # boleto/PDF ficam na conta do 1o mes
                **{
                    campo: dados[campo]
                    for campo in (
                        "numero_boleto", "pix", "beneficiario_cnpj", "documento_base64",
                        "documento_nome", "documento_tipo",
                    )
                    if campo in dados
                },
            },)
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
