from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QStackedWidget,
    QMessageBox,
)

from services.caixa_service import resumo_caixa, fechar_caixa


class FecharCaixaWindow(QDialog):

    def __init__(self):
        super().__init__()

        self.resumo = resumo_caixa() or {}
        self.valor_contado = 0.0

        self.setWindowTitle("Fechar Caixa")
        self.setFixedSize(460, 640)
        self.setStyleSheet("background:white;")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        cabecalho = QFrame()
        cabecalho.setStyleSheet("background:#202225;")
        cabecalho.setFixedHeight(70)

        cab_layout = QVBoxLayout(cabecalho)
        cab_layout.setContentsMargins(24, 12, 24, 12)
        cab_layout.setSpacing(2)

        self.lbl_titulo = QLabel("CONFERÊNCIA DE CAIXA")
        self.lbl_titulo.setStyleSheet(
            "background:transparent; color:white; "
            "font-size:16px; font-weight:bold;"
        )

        self.lbl_subtitulo = QLabel(
            "Conte o dinheiro em espécie na gaveta"
        )
        self.lbl_subtitulo.setStyleSheet(
            "background:transparent; color:#aaaaaa; font-size:11px;"
        )

        cab_layout.addWidget(self.lbl_titulo)
        cab_layout.addWidget(self.lbl_subtitulo)

        raiz.addWidget(cabecalho)

        self.paginas = QStackedWidget()

        self.pagina_contagem = self._criar_pagina_contagem()
        self.pagina_conferencia = self._criar_pagina_conferencia()

        self.paginas.addWidget(self.pagina_contagem)
        self.paginas.addWidget(self.pagina_conferencia)

        raiz.addWidget(self.paginas, stretch=1)

    # ======================================
    # PÁGINA 1 · CONTAGEM CEGA
    # ======================================

    def _criar_pagina_contagem(self):

        pagina = QFrame()

        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        aviso = QLabel(
            "Some todo o dinheiro físico presente na gaveta e "
            "informe o valor total contado. O sistema comparará "
            "com o valor esperado somente depois da contagem."
        )
        aviso.setWordWrap(True)
        aviso.setStyleSheet("""
            background:#FFF3E0;
            color:#E65100;
            font-size:12px;
            border-radius:8px;
            padding:12px;
        """)

        layout.addWidget(aviso)

        lbl_valor_titulo = QLabel("VALOR CONTADO EM ESPÉCIE")
        lbl_valor_titulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        self.valor_input = QLineEdit()
        self.valor_input.setPlaceholderText("R$ 0,00")
        self.valor_input.setAlignment(Qt.AlignCenter)
        self.valor_input.setStyleSheet("""
            QLineEdit {
                font-size:40px;
                font-weight:bold;
                color:#202225;
                border:none;
                border-bottom:2px solid #e0e0e0;
                padding:10px 0;
            }
        """)

        layout.addWidget(lbl_valor_titulo)
        layout.addWidget(self.valor_input)

        layout.addStretch()

        rodape = QHBoxLayout()

        bt_cancelar = QPushButton("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setStyleSheet("""
            QPushButton {
                background:white;
                color:#202225;
                border:1px solid #cccccc;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#f4f5f7;
            }
        """)
        bt_cancelar.clicked.connect(self.reject)

        bt_continuar = QPushButton("Continuar")
        bt_continuar.setMinimumHeight(46)
        bt_continuar.setStyleSheet("""
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
        bt_continuar.clicked.connect(self.avancar_para_conferencia)

        rodape.addWidget(bt_cancelar)
        rodape.addWidget(bt_continuar)

        layout.addLayout(rodape)

        return pagina

    def avancar_para_conferencia(self):

        try:
            self.valor_contado = float(
                self.valor_input.text().replace(",", ".")
            )
        except ValueError:
            QMessageBox.warning(
                self,
                "Atenção",
                "Informe o valor contado na gaveta.",
            )
            return

        if self.valor_contado < 0:
            QMessageBox.warning(
                self,
                "Atenção",
                "Informe um valor válido.",
            )
            return

        self.preencher_conferencia()

        self.lbl_titulo.setText("RESUMO DO FECHAMENTO")
        self.lbl_subtitulo.setText(
            "Confira os valores antes de encerrar o caixa"
        )

        self.paginas.setCurrentWidget(self.pagina_conferencia)

    # ======================================
    # PÁGINA 2 · CONFERÊNCIA
    # ======================================

    def _linha_valor(self, rotulo, cor="#202225"):

        linha = QHBoxLayout()

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(
            "background:transparent; border:none; "
            "font-size:13px; color:#555;"
        )

        lbl_valor = QLabel("R$ 0,00")
        lbl_valor.setAlignment(Qt.AlignRight)
        lbl_valor.setStyleSheet(
            f"background:transparent; border:none; font-size:13px; "
            f"font-weight:bold; color:{cor};"
        )

        linha.addWidget(lbl_rotulo)
        linha.addWidget(lbl_valor)

        return linha, lbl_valor

    def _separador(self):

        linha = QFrame()
        linha.setFixedHeight(1)
        linha.setStyleSheet("background:#e0e0e0; border:none;")
        return linha

    def _criar_pagina_conferencia(self):

        pagina = QFrame()

        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        bloco_previsto = QFrame()
        bloco_previsto.setStyleSheet(
            "background:#f4f5f7; border-radius:8px;"
        )
        bloco_layout = QVBoxLayout(bloco_previsto)
        bloco_layout.setContentsMargins(16, 14, 16, 14)
        bloco_layout.setSpacing(8)

        linha, self.lbl_troco_inicial = self._linha_valor("Troco inicial")
        bloco_layout.addLayout(linha)

        linha, self.lbl_vendas_dinheiro = self._linha_valor(
            "Vendas em dinheiro"
        )
        bloco_layout.addLayout(linha)

        linha, self.lbl_suprimentos = self._linha_valor(
            "Suprimentos", cor="#2E7D32"
        )
        bloco_layout.addLayout(linha)

        linha, self.lbl_sangrias = self._linha_valor(
            "Sangrias", cor="#C62828"
        )
        bloco_layout.addLayout(linha)

        bloco_layout.addWidget(self._separador())

        linha, self.lbl_total_previsto = self._linha_valor(
            "Total previsto em espécie", cor="#1565C0"
        )
        bloco_layout.addLayout(linha)

        layout.addWidget(bloco_previsto)

        bloco_contado = QFrame()
        bloco_contado.setStyleSheet(
            "background:white; border:1px solid #e0e0e0; "
            "border-radius:8px;"
        )
        contado_layout = QVBoxLayout(bloco_contado)
        contado_layout.setContentsMargins(16, 14, 16, 14)
        contado_layout.setSpacing(8)

        linha, self.lbl_valor_contado = self._linha_valor(
            "Valor contado"
        )
        contado_layout.addLayout(linha)

        contado_layout.addWidget(self._separador())

        linha, self.lbl_diferenca = self._linha_valor("Diferença")
        contado_layout.addLayout(linha)

        layout.addWidget(bloco_contado)

        bloco_outros = QFrame()
        bloco_outros.setStyleSheet(
            "background:#f4f5f7; border-radius:8px;"
        )
        outros_layout = QVBoxLayout(bloco_outros)
        outros_layout.setContentsMargins(16, 14, 16, 14)
        outros_layout.setSpacing(8)

        linha, self.lbl_vendas_pix = self._linha_valor("Vendas PIX")
        outros_layout.addLayout(linha)

        linha, self.lbl_vendas_cartao = self._linha_valor("Vendas cartão")
        outros_layout.addLayout(linha)

        outros_layout.addWidget(self._separador())

        linha, self.lbl_total_geral = self._linha_valor(
            "Total geral do turno", cor="#1565C0"
        )
        outros_layout.addLayout(linha)

        layout.addWidget(bloco_outros)

        layout.addStretch()

        rodape = QHBoxLayout()

        bt_voltar = QPushButton("Voltar")
        bt_voltar.setMinimumHeight(46)
        bt_voltar.setStyleSheet("""
            QPushButton {
                background:white;
                color:#202225;
                border:1px solid #cccccc;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#f4f5f7;
            }
        """)
        bt_voltar.clicked.connect(
            lambda: self.paginas.setCurrentWidget(self.pagina_contagem)
        )

        bt_confirmar = QPushButton("Confirmar Fechamento")
        bt_confirmar.setMinimumHeight(46)
        bt_confirmar.setStyleSheet("""
            QPushButton {
                background:#C62828;
                color:white;
                font-weight:bold;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#B71C1C;
            }
        """)
        bt_confirmar.clicked.connect(self.confirmar_fechamento)

        rodape.addWidget(bt_voltar)
        rodape.addWidget(bt_confirmar)

        layout.addLayout(rodape)

        return pagina

    def preencher_conferencia(self):

        r = self.resumo

        saldo_inicial = float(r.get("saldo_inicial", 0) or 0)
        vendas_dinheiro = float(r.get("vendas_dinheiro", 0) or 0)
        suprimentos = float(r.get("suprimentos", 0) or 0)
        sangrias = float(r.get("sangrias", 0) or 0)
        total_previsto = float(r.get("total_previsto", 0) or 0)
        vendas_pix = float(r.get("vendas_pix", 0) or 0)
        vendas_cartao = float(r.get("vendas_cartao", 0) or 0)
        total_geral = float(r.get("total_geral", 0) or 0)

        self.lbl_troco_inicial.setText(f"R$ {saldo_inicial:.2f}")
        self.lbl_vendas_dinheiro.setText(f"R$ {vendas_dinheiro:.2f}")
        self.lbl_suprimentos.setText(f"+ R$ {suprimentos:.2f}")
        self.lbl_sangrias.setText(f"- R$ {sangrias:.2f}")
        self.lbl_total_previsto.setText(f"R$ {total_previsto:.2f}")

        self.lbl_valor_contado.setText(f"R$ {self.valor_contado:.2f}")

        diferenca = self.valor_contado - total_previsto

        if abs(diferenca) < 0.01:
            cor = "#2E7D32"
            texto = "R$ 0,00 (confere)"
        elif diferenca > 0:
            cor = "#1565C0"
            texto = f"+ R$ {diferenca:.2f} (sobra)"
        else:
            cor = "#C62828"
            texto = f"- R$ {abs(diferenca):.2f} (falta)"

        self.lbl_diferenca.setText(texto)
        self.lbl_diferenca.setStyleSheet(
            f"background:transparent; border:none; font-size:13px; "
            f"font-weight:bold; color:{cor};"
        )

        self.lbl_vendas_pix.setText(f"R$ {vendas_pix:.2f}")
        self.lbl_vendas_cartao.setText(f"R$ {vendas_cartao:.2f}")
        self.lbl_total_geral.setText(f"R$ {total_geral:.2f}")

    def confirmar_fechamento(self):

        resposta = QMessageBox.question(
            self,
            "Fechar Caixa",
            "Confirmar o fechamento do caixa? Esta ação não "
            "pode ser desfeita.",
        )

        if resposta != QMessageBox.Yes:
            return

        response = fechar_caixa(
            valor_contado=self.valor_contado,
            observacoes=None,
        )

        if response.status_code == 200:
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", erro)
