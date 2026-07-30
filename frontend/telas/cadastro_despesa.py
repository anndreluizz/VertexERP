from datetime import date, datetime

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDateEdit,
    QComboBox,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
    QMessageBox,
)

from services.conta_pagar_service import (
    cadastrar_conta_pagar,
    atualizar_conta_pagar,
)
from services.categoria_despesa_service import listar_categorias_despesa
from telas.gerenciar_categorias_despesa import (
    GerenciarCategoriasDespesaDialog,
)

from design import tokens
from design.widgets import BotaoPerigo, BotaoSecundario, CampoTexto


def _formatar_moeda(valor):
    return (
        f"R$ {float(valor):,.2f}".replace(",", "X")
        .replace(".", ",").replace("X", ".")
    )


def _parse_valor(texto):
    try:
        return max(0.0, float(
            (texto or "").strip().replace(".", "").replace(",", ".") or 0
        ))
    except ValueError:
        return 0.0


class CadastroDespesaDialog(QDialog):

    def __init__(self, conta=None, duplicar_de=None, parent=None):

        super().__init__(parent)

        self.conta = conta
        self.conta_salva = None

        editando = conta is not None

        self.setWindowTitle(
            "Editar Despesa" if editando else "Nova Despesa"
        )
        self.setFixedWidth(440)
        self.resize(440, 680)
        self.setStyleSheet(f"background:{tokens.CARD};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QFrame()
        cabecalho.setStyleSheet(f"background:{tokens.SIDEBAR};")
        cabecalho.setFixedHeight(70)

        cab_layout = QVBoxLayout(cabecalho)
        cab_layout.setContentsMargins(24, 12, 24, 12)
        cab_layout.setSpacing(2)

        titulo = QLabel(
            "EDITAR DESPESA" if editando else "NOVA DESPESA"
        )
        titulo.setStyleSheet(f"""
            background:transparent; color:white;
            font-size:{tokens.TAMANHO_LG}px; font-weight:800;
        """)

        subtitulo = QLabel("Contas e despesas do estabelecimento")
        subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        cab_layout.addWidget(titulo)
        cab_layout.addWidget(subtitulo)

        raiz.addWidget(cabecalho)

        # ======================
        # CORPO (rolável)
        # ======================

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        corpo_widget = QWidget()
        corpo_widget.setStyleSheet(f"background:{tokens.CARD};")

        corpo_scroll_layout = QVBoxLayout(corpo_widget)
        corpo_scroll_layout.setContentsMargins(24, 20, 24, 20)
        corpo_scroll_layout.setSpacing(12)

        self.descricao = self._campo(
            corpo_scroll_layout, "DESCRIÇÃO", "Ex: aluguel, funcionária, luz..."
        )

        cabecalho_categoria = QHBoxLayout()

        lbl_categoria = QLabel("CATEGORIA")
        lbl_categoria.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        bt_gerenciar_categorias = QPushButton("Gerenciar")
        bt_gerenciar_categorias.setAutoDefault(False)
        bt_gerenciar_categorias.setCursor(Qt.PointingHandCursor)
        bt_gerenciar_categorias.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_XS}px; font-weight:700;
            }}
            QPushButton:hover {{ color:{tokens.PRIMARIA_HOVER}; }}
        """)
        bt_gerenciar_categorias.clicked.connect(self.gerenciar_categorias)

        cabecalho_categoria.addWidget(lbl_categoria)
        cabecalho_categoria.addStretch()
        cabecalho_categoria.addWidget(bt_gerenciar_categorias)

        self.categoria = QComboBox()
        self.categoria.setMinimumHeight(44)
        self.categoria.setCursor(Qt.PointingHandCursor)
        self.categoria.setStyleSheet(f"""
            QComboBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
            }}
        """)
        self._carregar_categorias()

        corpo_scroll_layout.addLayout(cabecalho_categoria)
        corpo_scroll_layout.addWidget(self.categoria)

        self.valor = self._campo(corpo_scroll_layout, "VALOR (R$)", "0,00")
        self.valor.textChanged.connect(self._atualizar_valor_final)

        lbl_vencimento = QLabel("VENCIMENTO")
        lbl_vencimento.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.vencimento = QDateEdit()
        self.vencimento.setCalendarPopup(True)
        self.vencimento.setDisplayFormat("dd/MM/yyyy")
        self.vencimento.setDate(QDate.currentDate())
        self.vencimento.setMinimumHeight(44)
        self.vencimento.setStyleSheet(f"""
            QDateEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
            }}
        """)

        corpo_scroll_layout.addWidget(lbl_vencimento)
        corpo_scroll_layout.addWidget(self.vencimento)

        self.numero_boleto = self._campo(
            corpo_scroll_layout,
            "CÓDIGO DE BARRAS (BOLETO)",
            "Bipe o boleto ou digite a linha digitável",
        )

        self.observacoes = self._campo(
            corpo_scroll_layout,
            "OBSERVAÇÕES",
            "Anotações internas sobre essa despesa",
        )

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
        corpo_scroll_layout.addWidget(self.bt_alternar_ajuste)

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

        self.desconto = self._campo_ajuste(linha_ajuste, "DESCONTO")
        self.juros = self._campo_ajuste(linha_ajuste, "JUROS")
        self.multa = self._campo_ajuste(linha_ajuste, "MULTA")

        ajuste_layout.addLayout(linha_ajuste)

        linha_final = QHBoxLayout()

        lbl_final_titulo = QLabel("VALOR FINAL (será salvo)")
        lbl_final_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
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

        corpo_scroll_layout.addWidget(self.bloco_ajuste)

        corpo_scroll_layout.addStretch()

        scroll.setWidget(corpo_widget)
        raiz.addWidget(scroll, stretch=1)

        # ======================
        # RODAPÉ
        # ======================

        rodape = QFrame()
        rodape.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-top:1px solid {tokens.BORDA};
        """)

        rodape_layout = QHBoxLayout(rodape)
        rodape_layout.setContentsMargins(24, 14, 24, 14)
        rodape_layout.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        self.bt_salvar = BotaoPerigo(
            "Salvar Alterações" if editando else "Cadastrar Despesa"
        )
        self.bt_salvar.setMinimumHeight(46)
        self.bt_salvar.setAutoDefault(False)
        self.bt_salvar.clicked.connect(self.salvar)

        rodape_layout.addWidget(bt_cancelar)
        rodape_layout.addWidget(self.bt_salvar)

        raiz.addWidget(rodape)

        if editando:
            self._preencher(conta)
        elif duplicar_de:
            self._preencher(duplicar_de, duplicando=True)

        self._atualizar_valor_final()

        self.descricao.setFocus()

    # ======================================

    def _campo(self, layout, rotulo, placeholder):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        campo = CampoTexto(placeholder)
        campo.setMinimumHeight(44)

        layout.addWidget(lbl)
        layout.addWidget(campo)

        return campo

    def _campo_ajuste(self, layout, rotulo):

        col = QVBoxLayout()
        col.setSpacing(4)

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
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

        self.lbl_valor_final.setText(_formatar_moeda(final))

        return final

    def _carregar_categorias(self):

        selecionada = self.categoria.currentText()

        self.categoria.clear()

        nomes = [
            c["nome"] for c in listar_categorias_despesa()
        ]

        self.categoria.addItems(nomes)

        if selecionada and self.categoria.findText(selecionada) >= 0:
            self.categoria.setCurrentText(selecionada)

    def gerenciar_categorias(self):

        dialogo = GerenciarCategoriasDespesaDialog(parent=self)
        dialogo.exec()

        self._carregar_categorias()

    def _preencher(self, conta, duplicando=False):

        self.descricao.setText(conta.get("descricao") or "")
        categoria = conta.get("categoria")
        if categoria and self.categoria.findText(categoria) >= 0:
            self.categoria.setCurrentText(categoria)

        if not duplicando:
            self.numero_boleto.setText(conta.get("numero_boleto") or "")
            self.observacoes.setText(conta.get("observacao") or "")

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

        dados = {
            "descricao": descricao,
            "categoria": self.categoria.currentText(),
            "valor": valor,
            "data_vencimento": data_vencimento,
            "numero_boleto": self.numero_boleto.text().strip() or None,
            "observacao": self.observacoes.text().strip() or None,
        }

        if self.conta:
            response = atualizar_conta_pagar(
                self.conta["id"],
                dados,
            )
        else:
            response = cadastrar_conta_pagar(dados)

        if response.status_code in (200, 201):

            self.conta_salva = response.json()

            self.accept()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))
