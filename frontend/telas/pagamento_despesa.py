import base64
import mimetypes
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QStackedWidget,
    QFileDialog,
    QMessageBox,
)

from services.api import configuracoes
from services.conta_pagar_service import atualizar_conta_pagar, pagar_conta_pagar
from services.worker import rodar_em_thread


def _confirmar_pagamento(conta_id, observacao_final, forma_pagamento, comprovante_base64, comprovante_nome, comprovante_tipo):
    """Roda na worker thread -- as 2 chamadas sequenciais que
    confirmar() precisa (atualiza observacao, depois marca como
    pago)."""

    response_obs = atualizar_conta_pagar(conta_id, {"observacao": observacao_final})

    if response_obs.status_code != 200:
        return response_obs, None

    response = pagar_conta_pagar(
        conta_id,
        forma_pagamento=forma_pagamento,
        comprovante_base64=comprovante_base64,
        comprovante_nome=comprovante_nome,
        comprovante_tipo=comprovante_tipo,
    )

    config = configuracoes() if response.status_code == 200 else {}

    return response_obs, response, config

from design import tokens
from design.responsive import tamanho_fixo_seguro
from design.widgets import (
    BotaoPerigo,
    BotaoSecundario,
    BotaoSucesso,
    CabecalhoDialogo,
    CampoTexto,
)
from utils.formatacao import formatar_moeda


FORMAS_PAGAMENTO = [
    ("Dinheiro", "DINHEIRO"),
    ("PIX", "PIX"),
    ("Cartão", "CARTAO"),
    ("Transferência", "TRANSFERENCIA"),
    ("Cheque", "CHEQUE"),
]

NOMES_FORMA = {valor: rotulo for rotulo, valor in FORMAS_PAGAMENTO}


class PagamentoDespesaDialog(QDialog):
    """Confirmação antes de marcar uma despesa como paga. A forma
    escolhida aqui vai pro backend em /pagar (só DINHEIRO mexe no
    saldo do caixa, ver ContaPagarService.pagar) -- e também vira um
    texto legível gravado no campo `observacao` (que já existe) via um
    PATCH logo antes, pra ficar visível no histórico da despesa sem
    precisar abrir o extrato do caixa pra saber como foi pago."""

    def __init__(self, conta, parent=None):

        super().__init__(parent)

        self.conta = conta
        self.forma_pagamento = "DINHEIRO"
        self._pagamento_confirmado = False
        self.comprovante_bytes = None
        self.comprovante_nome_arquivo = None
        self.comprovante_tipo_arquivo = None

        self.setWindowTitle("Pagamento de Despesa")
        tamanho_fixo_seguro(self, 480, 560)
        self.setStyleSheet(f"background:{tokens.CARD};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self.cabecalho = CabecalhoDialogo(
            "credit-card", tokens.SUCESSO, tokens.SUCESSO_CLARO,
            "Confirmar Pagamento", "Revise os dados antes de confirmar",
        )
        raiz.addWidget(self.cabecalho)

        self.paginas = QStackedWidget()

        self.pagina_confirmacao = self._construir_pagina_confirmacao()
        self.pagina_comprovante = self._construir_pagina_comprovante()

        self.paginas.addWidget(self.pagina_confirmacao)
        self.paginas.addWidget(self.pagina_comprovante)

        raiz.addWidget(self.paginas, stretch=1)

    # ======================================
    # PÁGINA 1 · CONFIRMAÇÃO
    # ======================================

    def _construir_pagina_confirmacao(self):

        pagina = QFrame()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        bloco_dados = QFrame()
        bloco_dados.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
        """)

        dados_layout = QVBoxLayout(bloco_dados)
        dados_layout.setContentsMargins(16, 14, 16, 14)
        dados_layout.setSpacing(6)

        self.lbl_categoria = self._linha_dado(dados_layout, "Categoria")
        self.lbl_descricao = self._linha_dado(dados_layout, "Descrição")
        self.lbl_vencimento = self._linha_dado(dados_layout, "Vencimento")
        self.lbl_valor = self._linha_dado(dados_layout, "Valor", destaque=True)

        layout.addWidget(bloco_dados)

        lbl_forma_titulo = QLabel("Forma de pagamento")
        lbl_forma_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(lbl_forma_titulo)

        formas_layout = QGridLayout()
        formas_layout.setSpacing(8)

        self.botoes_forma = {}

        for indice, (rotulo, valor) in enumerate(FORMAS_PAGAMENTO):

            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setAutoDefault(False)
            bt.setMinimumHeight(44)
            bt.clicked.connect(
                lambda checked, v=valor: self.selecionar_forma(v)
            )

            self.botoes_forma[valor] = bt
            formas_layout.addWidget(bt, indice // 3, indice % 3)

        layout.addLayout(formas_layout)

        lbl_obs_titulo = QLabel("Observação (opcional)")
        lbl_obs_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.observacao = CampoTexto("Ex: pago com desconto combinado...")

        layout.addWidget(lbl_obs_titulo)
        layout.addWidget(self.observacao)

        lbl_comprovante_titulo = QLabel("Comprovante (opcional)")
        lbl_comprovante_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(lbl_comprovante_titulo)

        linha_comprovante = QHBoxLayout()
        linha_comprovante.setSpacing(8)

        bt_anexar_comprovante = QPushButton("Anexar Comprovante")
        bt_anexar_comprovante.setCursor(Qt.PointingHandCursor)
        bt_anexar_comprovante.setAutoDefault(False)
        bt_anexar_comprovante.setMinimumHeight(38)
        bt_anexar_comprovante.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.FUNDO}; border:1.5px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px; padding:0 14px;
                font-size:{tokens.TAMANHO_SM}px; font-weight:600; color:{tokens.TEXTO};
            }}
            QPushButton:hover {{ background:{tokens.BORDA}; }}
        """)
        bt_anexar_comprovante.clicked.connect(self.escolher_comprovante)

        self.lbl_comprovante_anexado = QLabel("Nenhum arquivo anexado")
        self.lbl_comprovante_anexado.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)
        self.lbl_comprovante_anexado.setWordWrap(True)

        linha_comprovante.addWidget(bt_anexar_comprovante)
        linha_comprovante.addWidget(self.lbl_comprovante_anexado, stretch=1)

        layout.addLayout(linha_comprovante)

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        self.bt_confirmar = BotaoSucesso("Confirmar Pagamento")
        self.bt_confirmar.setMinimumHeight(46)
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.clicked.connect(self.confirmar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(self.bt_confirmar)

        layout.addLayout(botoes)

        self.selecionar_forma("DINHEIRO")
        self._preencher_dados()

        return pagina

    def _linha_dado(self, layout, rotulo, destaque=False):

        linha = QHBoxLayout()

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tokens.TAMANHO_SM}px; color:{tokens.TEXTO_SECUNDARIO};
        """)

        lbl_valor = QLabel("—")
        lbl_valor.setAlignment(Qt.AlignRight)
        cor = tokens.SECUNDARIA_HOVER if destaque else tokens.TEXTO
        tamanho = tokens.TAMANHO_LG if destaque else tokens.TAMANHO_SM
        lbl_valor.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tamanho}px; font-weight:700; color:{cor};
        """)

        linha.addWidget(lbl_rotulo)
        linha.addWidget(lbl_valor)

        layout.addLayout(linha)

        return lbl_valor

    def _preencher_dados(self):

        self.lbl_categoria.setText(self.conta.get("categoria") or "—")
        self.lbl_descricao.setText(self.conta.get("descricao") or "Despesa")

        try:
            venc = datetime.fromisoformat(
                self.conta["data_vencimento"]
            ).strftime("%d/%m/%Y")
        except (ValueError, TypeError, KeyError):
            venc = self.conta.get("data_vencimento", "—")

        self.lbl_vencimento.setText(venc)
        self.lbl_valor.setText(formatar_moeda(self.conta.get("valor", 0)))

    def selecionar_forma(self, valor):

        self.forma_pagamento = valor

        for chave, botao in self.botoes_forma.items():

            selecionado = chave == valor

            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.SECUNDARIA if selecionado else tokens.FUNDO};
                    color: {"white" if selecionado else tokens.TEXTO};
                    border-radius: {tokens.RADIUS_SM}px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background: {tokens.SECUNDARIA_HOVER if selecionado else tokens.BORDA};
                }}
            """)

    # mesmo motivo/limite de cadastro_despesa.py::escolher_documento --
    # sem isso, uma foto de celular sem compressao pode derrubar o
    # backend numa maquina de loja com pouca memoria
    _TAMANHO_MAX_COMPROVANTE = 8 * 1024 * 1024

    def escolher_comprovante(self):

        caminho, _ = QFileDialog.getOpenFileName(
            self, "Anexar Comprovante", "",
            "Documentos (*.pdf *.jpg *.jpeg *.png)",
        )

        if not caminho:
            return

        with open(caminho, "rb") as arquivo:
            conteudo = arquivo.read()

        if len(conteudo) > self._TAMANHO_MAX_COMPROVANTE:
            QMessageBox.warning(
                self, "Arquivo muito grande",
                "Esse arquivo passa de 8 MB. Anexe um PDF ou uma foto "
                "mais leve (tire com menos resolução ou comprima antes).",
            )
            return

        self.comprovante_bytes = conteudo

        nome_arquivo = caminho.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        self.comprovante_nome_arquivo = nome_arquivo
        self.comprovante_tipo_arquivo = (
            mimetypes.guess_type(caminho)[0] or "application/octet-stream"
        )

        self.lbl_comprovante_anexado.setText(nome_arquivo)
        self.lbl_comprovante_anexado.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO};
        """)

    def confirmar(self):

        observacao_atual = (self.conta.get("observacao") or "").strip()
        nota_pagamento = f"Pago via {NOMES_FORMA[self.forma_pagamento]}."

        observacao_usuario = self.observacao.text().strip()
        if observacao_usuario:
            nota_pagamento += f" {observacao_usuario}"

        observacao_final = (
            f"{observacao_atual}\n{nota_pagamento}"
            if observacao_atual else nota_pagamento
        )

        comprovante_base64 = (
            base64.b64encode(self.comprovante_bytes).decode("ascii")
            if self.comprovante_bytes else None
        )

        self.bt_confirmar.setEnabled(False)
        self._observacao_final_pendente = observacao_final

        rodar_em_thread(
            self,
            _confirmar_pagamento,
            self.conta["id"],
            observacao_final,
            self.forma_pagamento,
            comprovante_base64,
            self.comprovante_nome_arquivo,
            self.comprovante_tipo_arquivo,
            ao_sucesso=self._ao_confirmar_sucesso,
            ao_erro=self._ao_confirmar_erro,
            ao_finalizar=self._ao_confirmar_finalizado,
        )

    def _ao_confirmar_sucesso(self, resultado):

        response_obs, response, config = resultado

        if response_obs.status_code != 200:
            try:
                erro = response_obs.json()["detail"]
            except Exception:
                erro = response_obs.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        if response.status_code != 200:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        self._pagamento_confirmado = True

        self.cabecalho.definir_texto(
            "Pagamento Confirmado", "Despesa marcada como paga com sucesso"
        )
        self.cabecalho.definir_icone("check", tokens.SUCESSO)

        self._atualizar_comprovante(self._observacao_final_pendente, config)

        self.paginas.setCurrentWidget(self.pagina_comprovante)

    def _ao_confirmar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_confirmar_finalizado(self):
        self.bt_confirmar.setEnabled(True)

    def closeEvent(self, event):
        # o pagamento ja foi gravado no backend assim que chega na
        # pagina de comprovante — fechar a janela nesse ponto (pelo X
        # ou pelo botao) precisa sempre contar como Accepted pra quem
        # abriu o dialogo (ContasPagar) saber que precisa recarregar
        # a lista, mesmo que o usuario feche pelo X em vez do botao
        if self._pagamento_confirmado:
            self.accept()
        else:
            super().closeEvent(event)

    # ======================================
    # PÁGINA 2 · COMPROVANTE
    # ======================================

    def _construir_pagina_comprovante(self):

        pagina = QFrame()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        self.lbl_comprovante = QLabel()
        self.lbl_comprovante.setWordWrap(True)
        self.lbl_comprovante.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.lbl_comprovante.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
            padding:16px; font-size:{tokens.TAMANHO_SM}px; color:{tokens.TEXTO};
        """)

        layout.addWidget(self.lbl_comprovante, stretch=1)

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_imprimir = BotaoSecundario("Imprimir", icone_nome="printer")
        bt_imprimir.setMinimumHeight(44)
        bt_imprimir.setAutoDefault(False)
        bt_imprimir.clicked.connect(self.imprimir_comprovante)

        bt_pdf = BotaoSecundario("Salvar PDF", icone_nome="download")
        bt_pdf.setMinimumHeight(44)
        bt_pdf.setAutoDefault(False)
        bt_pdf.clicked.connect(self.salvar_pdf_comprovante)

        bt_whatsapp = BotaoSecundario("WhatsApp")
        bt_whatsapp.setMinimumHeight(44)
        bt_whatsapp.setEnabled(False)
        bt_whatsapp.setToolTip("Em breve")

        botoes.addWidget(bt_imprimir)
        botoes.addWidget(bt_pdf)
        botoes.addWidget(bt_whatsapp)

        layout.addLayout(botoes)

        bt_fechar = BotaoPerigo("Fechar")
        bt_fechar.setMinimumHeight(46)
        bt_fechar.setAutoDefault(False)
        bt_fechar.clicked.connect(self.accept)

        layout.addWidget(bt_fechar)

        return pagina

    def _atualizar_comprovante(self, observacao_final, config):

        nome_loja = config.get("nome_loja") or "Vertex ERP"

        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        texto = (
            f"<b>{nome_loja}</b><br>"
            f"<span style='color:#888;'>Comprovante de pagamento — "
            f"não fiscal</span><br><br>"
            f"<b>Descrição:</b> {self.conta.get('descricao') or 'Despesa'}<br>"
            f"<b>Categoria:</b> {self.conta.get('categoria') or '—'}<br>"
            f"<b>Valor pago:</b> {formatar_moeda(self.conta.get('valor', 0))}<br>"
            f"<b>Forma de pagamento:</b> {NOMES_FORMA[self.forma_pagamento]}<br>"
            f"<b>Data:</b> {agora}<br><br>"
            f"{observacao_final.replace(chr(10), '<br>')}"
        )

        self._texto_comprovante = texto
        self.lbl_comprovante.setText(texto)

    def _montar_documento_comprovante(self):

        documento = QTextDocument()
        documento.setDefaultFont(QFont(tokens.FONTE_FAMILIA_PADRAO, 10))
        documento.setHtml(self._texto_comprovante)

        return documento

    def imprimir_comprovante(self):

        printer = QPrinter(QPrinter.HighResolution)

        dialogo = QPrintDialog(printer, self)

        if dialogo.exec() != QPrintDialog.Accepted:
            return

        self._montar_documento_comprovante().print_(printer)

    def salvar_pdf_comprovante(self):

        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Comprovante",
            "comprovante_pagamento.pdf",
            "Arquivo PDF (*.pdf)",
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(caminho)
        printer.setPageSize(QPageSize(QPageSize.A5))

        self._montar_documento_comprovante().print_(printer)

        QMessageBox.information(
            self, "Sucesso", "Comprovante salvo em PDF com sucesso."
        )
