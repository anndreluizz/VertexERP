import base64
import winsound
from datetime import datetime, timedelta

from telas.pagamento import PagamentoWindow
from services.venda_service import finalizar_venda as enviar_venda
from services.pdv_service import buscar_produto
from services.produto_service import listar_produtos
from services.fiado_service import registrar_pagamento
from services.configuracao_service import (
    buscar_configuracoes,
    buscar_logo_bytes,
)

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView,
    QMessageBox,
)

TABELA_ESTILO = """
    QTableWidget {
        background: #1e1e1e;
        gridline-color: #333;
        border: none;
    }
    QTableWidget::item {
        padding: 4px;
    }
    QTableWidget::item:selected {
        background: #1565C0;
    }
    QHeaderView::section {
        background: #2b2b2b;
        color: white;
        font-weight: bold;
        padding: 6px;
        border: none;
        border-bottom: 2px solid #1565C0;
    }
"""

CAMPO_ESTILO = """
    QLineEdit {
        padding: 8px;
        border: 1px solid #444;
        border-radius: 6px;
        background: #2b2b2b;
    }
    QLineEdit:focus {
        border: 1px solid #1565C0;
    }
"""

FORMAS_PAGAMENTO_LABEL = {
    "DINHEIRO": "Dinheiro",
    "PIX": "PIX",
    "DEBITO": "Cartão de Débito",
    "CREDITO": "Cartão de Crédito",
    "PRAZO": "Prazo (Fiado)",
}


class PDV(QWidget):

    def __init__(self):
        super().__init__()

        self.itens = []
        self.produtos = []

        layout = QVBoxLayout(self)

        titulo = QLabel("PONTO DE VENDA")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        area = QHBoxLayout()
        area.setSpacing(16)

        self.frame_produtos = self._montar_painel_produtos()
        area.addWidget(self.frame_produtos, 2)
        area.addWidget(self._montar_painel_venda(), 3)

        layout.addLayout(area)

        # O painel de busca por grade é um apoio pra quando o código de
        # barras falha — o fluxo normal é só escanear, então ele começa
        # fechado pra não disputar espaço/atenção com o carrinho.
        self.frame_produtos.setVisible(False)

        # ==========================================
        # ATALHOS DE TECLADO
        # ==========================================
        QShortcut(QKeySequence("F2"), self, lambda: self.codigo.setFocus())
        QShortcut(QKeySequence("F3"), self, self.abrir_painel_produtos)
        QShortcut(QKeySequence("F4"), self, self.finalizar_venda)
        QShortcut(QKeySequence("Delete"), self, self.remover_item_selecionado)
        QShortcut(QKeySequence("Escape"), self, self.fechar_painel_produtos)

        # +/- só ativam com o foco na tabela do carrinho (não na janela
        # inteira) — assim não conflitam com o campo de código, onde "+"
        # ou "-" digitado por engano corromperia o código de barras.
        self._atalho_mais = QShortcut(QKeySequence("+"), self.tabela)
        self._atalho_mais.setContext(Qt.WidgetWithChildrenShortcut)
        self._atalho_mais.activated.connect(self.aumentar_quantidade_selecionada)

        self._atalho_menos = QShortcut(QKeySequence("-"), self.tabela)
        self._atalho_menos.setContext(Qt.WidgetWithChildrenShortcut)
        self._atalho_menos.activated.connect(self.diminuir_quantidade_selecionada)

        self.carregar_produtos()

        self.codigo.setFocus()

    # ==================================================
    # ABRIR/FECHAR PAINEL DE PRODUTOS
    # ==================================================

    def abrir_painel_produtos(self):
        self.frame_produtos.setVisible(True)
        self.busca_produto.setFocus()

    def fechar_painel_produtos(self):
        self.frame_produtos.setVisible(False)
        self.codigo.setFocus()

    def alternar_painel_produtos(self):
        if self.frame_produtos.isVisible():
            self.fechar_painel_produtos()
        else:
            self.abrir_painel_produtos()

    # ==================================================
    # PAINEL DE PRODUTOS (ESQUERDA)
    # ==================================================

    def _montar_painel_produtos(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #232323;
                border: 1px solid #333;
                border-radius: 10px;
            }
        """)

        painel = QVBoxLayout(frame)
        painel.setContentsMargins(14, 14, 14, 14)
        painel.setSpacing(10)

        titulo = QLabel("📦 Produtos")
        titulo.setStyleSheet("font-size:16px; font-weight:bold; border:none;")
        painel.addWidget(titulo)

        self.busca_produto = QLineEdit()
        self.busca_produto.setPlaceholderText(
            "Buscar produto por nome ou código (F3)"
        )
        self.busca_produto.setStyleSheet(CAMPO_ESTILO)
        self.busca_produto.textChanged.connect(self.filtrar_produtos)
        painel.addWidget(self.busca_produto)

        self.tabela_produtos = QTableWidget()
        self.tabela_produtos.setColumnCount(4)
        self.tabela_produtos.setHorizontalHeaderLabels([
            "Código",
            "Produto",
            "Preço",
            "Estoque",
        ])
        self.tabela_produtos.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela_produtos.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela_produtos.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela_produtos.setAlternatingRowColors(True)
        self.tabela_produtos.verticalHeader().setVisible(False)
        self.tabela_produtos.setStyleSheet(TABELA_ESTILO)
        self.tabela_produtos.verticalHeader().setDefaultSectionSize(32)
        self.tabela_produtos.doubleClicked.connect(
            self.adicionar_produto_da_grade
        )

        painel.addWidget(self.tabela_produtos)

        dica = QLabel("Duplo clique adiciona o produto ao carrinho")
        dica.setStyleSheet("color:#888; font-size:11px; border:none;")
        painel.addWidget(dica)

        return frame

    # ==================================================
    # PAINEL DE VENDA (DIREITA)
    # ==================================================

    def _montar_painel_venda(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #232323;
                border: 1px solid #333;
                border-radius: 10px;
            }
        """)

        painel = QVBoxLayout(frame)
        painel.setContentsMargins(14, 14, 14, 14)
        painel.setSpacing(10)

        titulo = QLabel("🛒 Carrinho")
        titulo.setStyleSheet("font-size:16px; font-weight:bold; border:none;")
        painel.addWidget(titulo)

        pesquisa = QHBoxLayout()

        self.codigo = QLineEdit()
        self.codigo.setPlaceholderText(
            "Código ou Código de Barras (F2) — ex: 3*código lança 3 unidades"
        )
        self.codigo.setStyleSheet(CAMPO_ESTILO)

        self.bt_buscar = QPushButton("Buscar")
        self.bt_buscar.setStyleSheet("""
            QPushButton {
                background:#1565C0;
                color:white;
                font-weight:bold;
                border:none;
                border-radius:6px;
                padding:8px 16px;
            }
            QPushButton:hover {
                background:#0D47A1;
            }
        """)

        self.bt_buscar.clicked.connect(
            self.adicionar_produto
        )

        self.codigo.returnPressed.connect(
            self.adicionar_produto
        )

        self.bt_toggle_produtos = QPushButton("🔍 (F3)")
        self.bt_toggle_produtos.setToolTip(
            "Buscar produto numa lista (quando o código de barras falha)"
        )
        self.bt_toggle_produtos.setStyleSheet("""
            QPushButton {
                background:#333;
                color:white;
                border:none;
                border-radius:6px;
                padding:8px 12px;
            }
            QPushButton:hover {
                background:#444;
            }
        """)
        self.bt_toggle_produtos.clicked.connect(
            self.alternar_painel_produtos
        )

        pesquisa.addWidget(self.codigo)
        pesquisa.addWidget(self.bt_buscar)
        pesquisa.addWidget(self.bt_toggle_produtos)

        painel.addLayout(pesquisa)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setVisible(False)
        painel.addWidget(self.status_label)

        self.tabela = QTableWidget()

        self.tabela.setColumnCount(5)

        self.tabela.setHorizontalHeaderLabels([
            "Código",
            "Produto",
            "Qtde",
            "Unitário",
            "Total",
        ])

        self.tabela.horizontalHeader().setStretchLastSection(True)
        self.tabela.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.verticalHeader().setDefaultSectionSize(32)
        self.tabela.setStyleSheet(TABELA_ESTILO)
        self.tabela.itemChanged.connect(self.item_alterado)

        painel.addWidget(self.tabela)

        dica = QLabel(
            "Duplo clique na Qtde pra editar   •   +/- aumenta/diminui   •   "
            "Delete remove o item selecionado"
        )
        dica.setStyleSheet("color:#888; font-size:11px; border:none;")
        painel.addWidget(dica)

        total_layout = QHBoxLayout()

        self.bt_cancelar = QPushButton("Cancelar Venda")
        self.bt_finalizar = QPushButton("Finalizar Venda (F4)")

        self.bt_cancelar.setMinimumHeight(45)
        self.bt_finalizar.setMinimumHeight(45)

        self.bt_cancelar.setStyleSheet("""
        QPushButton{
            background:#C62828;
            color:white;
            font-size:15px;
            font-weight:bold;
        }

        QPushButton:hover{
            background:#B71C1C;
        }
        """)

        self.bt_finalizar.setStyleSheet("""
        QPushButton{
            background:#2E7D32;
            color:white;
            font-size:15px;
            font-weight:bold;
        }

        QPushButton:hover{
            background:#1B5E20;
        }
        """)

        self.total = QLabel("TOTAL: R$ 0,00")

        self.total.setStyleSheet("""
            font-size:26px;
            font-weight:bold;
            color:#1565C0;
        """)

        total_layout.addWidget(self.bt_cancelar)
        total_layout.addStretch()
        total_layout.addWidget(self.total)
        total_layout.addStretch()
        total_layout.addWidget(self.bt_finalizar)

        painel.addLayout(total_layout)

        self.bt_cancelar.clicked.connect(
            self.cancelar_venda
        )

        self.bt_finalizar.clicked.connect(
            self.finalizar_venda
        )

        return frame

    # ==================================================
    # CARREGAR PRODUTOS NA GRADE
    # ==================================================

    def carregar_produtos(self):
        self.produtos = listar_produtos()
        self.preencher_tabela_produtos(self.produtos)

    # ==================================================
    # FILTRAR PRODUTOS
    # ==================================================

    def filtrar_produtos(self):
        texto = self.busca_produto.text().lower().strip()

        if texto == "":
            produtos = self.produtos
        else:
            produtos = [
                produto
                for produto in self.produtos
                if texto in produto["nome"].lower()
                or texto in str(produto.get("codigo") or "").lower()
                or texto in str(produto.get("codigo_barras") or "").lower()
            ]

        self.preencher_tabela_produtos(produtos)

    # ==================================================
    # PREENCHER TABELA DE PRODUTOS
    # ==================================================

    def preencher_tabela_produtos(self, produtos):
        self.tabela_produtos.setRowCount(len(produtos))

        for linha, produto in enumerate(produtos):
            self.tabela_produtos.setItem(
                linha, 0, QTableWidgetItem(produto["codigo"])
            )
            self.tabela_produtos.setItem(
                linha, 1, QTableWidgetItem(produto["nome"])
            )
            self.tabela_produtos.setItem(
                linha,
                2,
                QTableWidgetItem(f"R$ {float(produto['preco_venda']):.2f}"),
            )
            self.tabela_produtos.setItem(
                linha, 3, QTableWidgetItem(str(produto.get("estoque", 0)))
            )

    # ==================================================
    # ADICIONAR PRODUTO A PARTIR DA GRADE (DUPLO CLIQUE)
    # ==================================================

    def adicionar_produto_da_grade(self, index):
        linha = index.row()

        if linha < 0 or linha >= self.tabela_produtos.rowCount():
            return

        codigo = self.tabela_produtos.item(linha, 0).text()

        self.adicionar_produto(codigo)

        # Depois de achar na grade, volta pro fluxo normal de scan.
        self.fechar_painel_produtos()

    # ==================================================
    # STATUS NÃO-BLOQUEANTE + BEEP
    # ==================================================

    def _beep_sucesso(self):
        try:
            winsound.Beep(1500, 80)
        except Exception:
            pass

    def _beep_erro(self):
        try:
            winsound.Beep(300, 250)
        except Exception:
            pass

    def _status(self, mensagem, tipo="ok"):
        cores = {
            "ok": "#2E7D32",
            "erro": "#C62828",
        }

        self.status_label.setStyleSheet(
            "font-weight:bold; padding:6px; border-radius:6px; "
            f"background:{cores.get(tipo, '#1565C0')}; color:white;"
        )
        self.status_label.setText(mensagem)
        self.status_label.setVisible(True)

        QTimer.singleShot(
            2500, lambda: self.status_label.setVisible(False)
        )

    # ==================================================
    # ADICIONAR PRODUTO
    # ==================================================

    def adicionar_produto(self, codigo=None):

        quantidade_extra = 1

        if codigo is None:
            texto = self.codigo.text().strip()

            if "*" in texto:
                multiplicador, _, texto = texto.partition("*")
                multiplicador = multiplicador.strip()

                if multiplicador.isdigit() and int(multiplicador) > 0:
                    quantidade_extra = int(multiplicador)

            codigo = texto.strip()
        else:
            codigo = str(codigo).strip()

        if not codigo:
            return

        produto = buscar_produto(codigo)

        if produto is None:

            self._beep_erro()
            self._status("Produto não encontrado.", "erro")

            self.codigo.clear()
            self.codigo.setFocus()

            return

        encontrou = False

        for item in self.itens:

            if item["id"] == produto["id"]:

                item["quantidade"] += quantidade_extra

                encontrou = True

                break

        if not encontrou:

            self.itens.append(
                {
                    "id": produto["id"],
                    "codigo": produto["codigo"],
                    "nome": produto["nome"],
                    "preco": float(produto["preco"]),
                    "quantidade": quantidade_extra,
                }
            )

        self.atualizar_tabela()

        self._beep_sucesso()
        self._status(f"{produto['nome']} adicionado", "ok")

        self.codigo.clear()

        self.codigo.setFocus()

    # ==================================================
    # ATUALIZAR TABELA
    # ==================================================

    def atualizar_tabela(self):

        self.tabela.blockSignals(True)

        self.tabela.setRowCount(len(self.itens))

        total = 0

        for linha, item in enumerate(self.itens):
            subtotal = (
                    item["preco"] *
                    item["quantidade"]
            )

            total += subtotal

            codigo = QTableWidgetItem(item["codigo"])
            codigo.setFlags(codigo.flags() & ~Qt.ItemIsEditable)
            self.tabela.setItem(linha, 0, codigo)

            nome = QTableWidgetItem(item["nome"])
            nome.setFlags(nome.flags() & ~Qt.ItemIsEditable)
            self.tabela.setItem(linha, 1, nome)

            self.tabela.setItem(
                linha,
                2,
                QTableWidgetItem(str(item["quantidade"]))
            )

            unitario = QTableWidgetItem(f"R$ {item['preco']:.2f}")
            unitario.setFlags(unitario.flags() & ~Qt.ItemIsEditable)
            self.tabela.setItem(linha, 3, unitario)

            total_item = QTableWidgetItem(f"R$ {subtotal:.2f}")
            total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
            self.tabela.setItem(linha, 4, total_item)

        self.total.setText(
            f"TOTAL: R$ {total:.2f}"
        )

        self.tabela.blockSignals(False)

    # ==================================================
    # ITEM ALTERADO (EDIÇÃO DE QUANTIDADE)
    # ==================================================

    def item_alterado(self, item):

        linha = item.row()
        coluna = item.column()

        if linha >= len(self.itens) or coluna != 2:
            return

        try:
            quantidade = int(item.text())

            if quantidade <= 0:
                quantidade = 1

            self.itens[linha]["quantidade"] = quantidade

            self.atualizar_tabela()

        except Exception:
            QMessageBox.warning(
                self,
                "Aviso",
                "Quantidade inválida."
            )

            self.atualizar_tabela()

    # ==================================================
    # REMOVER ITEM SELECIONADO (DELETE)
    # ==================================================

    def remover_item_selecionado(self):

        linha = self.tabela.currentRow()

        if linha < 0 or linha >= len(self.itens):
            return

        del self.itens[linha]

        self.atualizar_tabela()

    # ==================================================
    # +/- QUANTIDADE DO ITEM SELECIONADO
    # ==================================================

    def aumentar_quantidade_selecionada(self):
        self._alterar_quantidade_selecionada(1)

    def diminuir_quantidade_selecionada(self):
        self._alterar_quantidade_selecionada(-1)

    def _alterar_quantidade_selecionada(self, delta):

        linha = self.tabela.currentRow()

        if linha < 0 or linha >= len(self.itens):
            return

        nova_quantidade = self.itens[linha]["quantidade"] + delta

        if nova_quantidade <= 0:
            return

        self.itens[linha]["quantidade"] = nova_quantidade

        self.atualizar_tabela()

        self.tabela.selectRow(linha)

    # ==================================================
    # CANCELAR VENDA
    # ==================================================

    def cancelar_venda(self):

        if not self.itens:
            return

        resposta = QMessageBox.question(
            self,
            "Cancelar Venda",
            "Deseja cancelar esta venda?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if resposta == QMessageBox.No:
            return

        self.itens.clear()

        self.tabela.setRowCount(0)

        self.total.setText(
            "TOTAL: R$ 0,00"
        )

        self.codigo.clear()

        self.codigo.setFocus()

    # ==================================================
    # FINALIZAR VENDA
    # ==================================================

    def finalizar_venda(self):

        if not self.itens:
            QMessageBox.warning(
                self,
                "Aviso",
                "Nenhum produto foi adicionado."
            )

            return

        total = sum(
            item["preco"] * item["quantidade"]
            for item in self.itens
        )

        tela = PagamentoWindow(total)

        if tela.exec() != QDialog.Accepted:
            return

        try:

            data_vencimento = None

            if tela.forma_pagamento == "PRAZO":
                # Fiado: vencimento padrão de 30 dias, sem pedir a data
                # ao operador do caixa (mantém o fluxo simples).
                data_vencimento = (
                    datetime.now() + timedelta(days=30)
                ).isoformat()

            response = enviar_venda(
                itens=self.itens,
                forma_pagamento=tela.forma_pagamento,
                cliente_id=tela.cliente_id,
                desconto=0,
                observacao=None,
                data_vencimento=data_vencimento,
            )

            if response.status_code == 201:

                venda = response.json()

                if tela.forma_pagamento == "PRAZO" and tela.valor_entrada > 0:
                    # Entrada paga no ato abate o fiado imediatamente,
                    # já que a venda inteira foi lançada como COMPRA.
                    registrar_pagamento(
                        cliente_id=tela.cliente_id,
                        valor=tela.valor_entrada,
                        descricao=f"Entrada na venda #{venda['id']}",
                    )

                impressora = None

                preferencia = (
                    buscar_configuracoes().get("impressao_comprovante")
                    or "perguntar"
                )

                deve_imprimir = preferencia == "sempre"

                if preferencia == "perguntar":
                    resposta = QMessageBox.question(
                        self,
                        "Imprimir Comprovante",
                        "Deseja imprimir o comprovante desta venda?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes,
                    )
                    deve_imprimir = resposta == QMessageBox.Yes

                if deve_imprimir:
                    impressora = self.imprimir_comprovante(venda, tela)

                self.itens.clear()

                self.tabela.setRowCount(0)

                self.total.setText(
                    "TOTAL: R$ 0,00"
                )

                self.codigo.clear()

                self.codigo.setFocus()

                self.carregar_produtos()

                self._beep_sucesso()

                mensagem = (
                    f"✅ Venda #{venda['id']} concluída — "
                    f"Total R$ {total:.2f}"
                )

                if impressora:
                    mensagem += f" — 🖨️ impresso em {impressora}"

                self._status(mensagem, "ok")

            else:

                try:
                    erro = response.json()

                    if isinstance(erro, dict):
                        erro = erro.get(
                            "detail",
                            str(erro)
                        )

                except Exception:
                    erro = response.text

                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Erro ao finalizar a venda.\n\n{erro}"
                )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Erro",
                str(e)
            )

    # ==================================================
    # IMPRIMIR COMPROVANTE
    # ==================================================

    def imprimir_comprovante(self, venda, tela):

        total = sum(
            item["preco"] * item["quantidade"]
            for item in self.itens
        )

        linhas_itens = ""

        for item in self.itens:
            subtotal = item["preco"] * item["quantidade"]

            linhas_itens += (
                "<tr>"
                f"<td>{item['nome']}</td>"
                f"<td align='center'>{item['quantidade']}</td>"
                f"<td align='right'>R$ {item['preco']:.2f}</td>"
                f"<td align='right'>R$ {subtotal:.2f}</td>"
                "</tr>"
            )

        cliente_html = ""

        if tela.cliente_id:
            cliente_html = f"<p>Cliente: {tela.cliente_nome}</p>"

        entrada_html = ""

        if tela.forma_pagamento == "PRAZO" and tela.valor_entrada > 0:
            entrada_html = (
                f"<p>Entrada paga: R$ {tela.valor_entrada:.2f} — "
                f"Restante no fiado: R$ {total - tela.valor_entrada:.2f}</p>"
            )

        forma = FORMAS_PAGAMENTO_LABEL.get(
            tela.forma_pagamento, tela.forma_pagamento
        )

        config = buscar_configuracoes()
        nome_loja = config.get("nome_loja") or "VERTEX ERP"

        cabecalho_loja = f"<h2 style='text-align:center;'>{nome_loja}</h2>"

        logo_bytes = buscar_logo_bytes()

        if logo_bytes:
            logo_base64 = base64.b64encode(logo_bytes).decode("ascii")
            cabecalho_loja = (
                "<p style='text-align:center;'>"
                f"<img src='data:image/png;base64,{logo_base64}' "
                "height='60'></p>"
            ) + cabecalho_loja

        dados_loja_html = ""

        detalhes_loja = " • ".join(
            filter(None, [config.get("cnpj_cpf"), config.get("telefone")])
        )

        if detalhes_loja:
            dados_loja_html += (
                f"<p style='text-align:center;'>{detalhes_loja}</p>"
            )

        if config.get("endereco"):
            dados_loja_html += (
                f"<p style='text-align:center;'>{config['endereco']}</p>"
            )

        html = f"""
        {cabecalho_loja}
        {dados_loja_html}
        <p style='text-align:center;'>Comprovante de Venda #{venda['id']}</p>
        <p>Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        {cliente_html}
        <table width='100%' cellspacing='0' cellpadding='4'>
            <tr>
                <th align='left'>Produto</th>
                <th align='center'>Qtde</th>
                <th align='right'>Unitário</th>
                <th align='right'>Subtotal</th>
            </tr>
            {linhas_itens}
        </table>
        <h3 style='text-align:right;'>TOTAL: R$ {total:.2f}</h3>
        <p>Forma de Pagamento: {forma}</p>
        {entrada_html}
        <p style='text-align:center;'>Obrigado pela preferência!</p>
        """

        try:
            impressora_padrao = QPrinterInfo.defaultPrinter()

            if impressora_padrao.isNull():
                QMessageBox.warning(
                    self,
                    "Impressão",
                    "Nenhuma impressora padrão configurada no Windows. "
                    "O comprovante não foi impresso."
                )
                return

            printer = QPrinter(
                impressora_padrao, QPrinter.HighResolution
            )

            documento = QTextDocument()
            documento.setHtml(html)
            documento.print_(printer)

            return impressora_padrao.printerName()

        except Exception as e:

            QMessageBox.warning(
                self,
                "Impressão",
                f"Não foi possível imprimir o comprovante.\n\n{e}"
            )

            return None
