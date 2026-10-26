import uuid

from telas.pagamento import PagamentoWindow
from telas.buscar_produto import BuscarProdutoDialog
from telas.venda_concluida import VendaConcluidaDialog
from telas.cadastro_produto import CadastroProdutoWindow
from telas.selecionar_cliente import SelecionarClienteDialog
from services.venda_service import (
    finalizar_venda as enviar_venda,
)
from services.worker import rodar_em_thread
from services.produto_service import (
    cadastrar_produto,
)
from services.pdv_service import buscar_produto
from services.caixa_service import caixa_aberto
from services.api import me
from services import preferencias_service
from PySide6.QtCore import Qt, QTimer, Signal, QEvent
from PySide6.QtGui import (
    QShortcut,
    QKeySequence,
    QCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QScrollArea,
    QMessageBox,
)
from design import tokens
from design.animations import fade_in
from utils.formatacao import formatar_moeda
from telas.pdv.carrinho import CarrinhoMixin
from telas.pdv.comum import (
    ATALHOS_PADRAO,
    LARGURA_PAINEL_RESUMO,
    _parse_data,
    _separar_multiplicador,
)
from telas.pdv.layout import LayoutMixin
from telas.pdv.orcamento import OrcamentoMixin
from telas.pdv.vendas_suspensas import VendasSuspensasMixin


class PDV(LayoutMixin, CarrinhoMixin, VendasSuspensasMixin, OrcamentoMixin, QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.itens = []
        # chave de idempotencia do carrinho atual (ver finalizar_venda)
        self._chave_venda = None
        self.cliente_id = None
        self.cliente_nome = None
        # troca na hora: valor da peça devolvida que abate desta venda
        # (ver iniciar_troca)
        self.credito_troca = 0.0
        self.desconto_valor = 0.0
        self.acrescimo_valor = 0.0
        self._finalizando_venda = False
        self._suspendendo_venda = False
        # destaque "ultimo item lido" -- id do produto, nao indice da
        # linha, pra continuar certo quando outra linha e' removida
        self._id_ultimo_item = None
        self._fotos_cache = {}

        self._usuario_id = (me() or {}).get("id")
        self.atalhos = self._carregar_atalhos()

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Cabeçalho — largura plena, acima das duas colunas.
        layout.addLayout(self._construir_cabecalho())

        # ======================
        # CORPO: carrinho fica numa área que rola se a janela for
        # baixa demais (mesma solução já usada antes pra não estourar
        # em notebooks/1366x768) — o painel de resumo financeiro +
        # botão Pagar fica de fora da rolagem, sempre visível, à
        # direita.
        # ======================

        corpo = QHBoxLayout()
        corpo.setContentsMargins(24, 4, 24, 20)
        corpo.setSpacing(20)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        # sem rolagem horizontal: o conteúdo se ajusta à largura. Antes,
        # a linha de favoritos empurrava a coluna pra além da tela e
        # aparecia uma barra de rolagem embaixo do cupom, com a borda
        # direita dos cards cortada
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        coluna_esquerda = QWidget()
        coluna_esquerda.setStyleSheet("background:transparent;")

        layout_esquerda = QVBoxLayout(coluna_esquerda)
        layout_esquerda.setContentsMargins(0, 0, 4, 0)
        layout_esquerda.setSpacing(12)

        # layout de caixa de loja: ultimo item em destaque, campo de
        # codigo, e a lista em formato de cupom; cliente/totais ficam
        # no painel da direita, com o TOTAL grande
        layout_esquerda.addWidget(self._construir_ultimo_item())
        layout_esquerda.addWidget(self._construir_campo_codigo())
        layout_esquerda.addWidget(self.lbl_status_busca)
        layout_esquerda.addWidget(self._construir_mais_vendidos())
        layout_esquerda.addWidget(self._construir_cartao_tabela(), stretch=1)

        self.tabela.setMinimumHeight(160)

        scroll.setWidget(coluna_esquerda)
        corpo.addWidget(scroll, stretch=1)

        painel_resumo = QWidget()
        painel_resumo.setFixedWidth(LARGURA_PAINEL_RESUMO)
        painel_resumo.setStyleSheet("background:transparent;")

        layout_resumo = QVBoxLayout(painel_resumo)
        layout_resumo.setContentsMargins(0, 0, 0, 0)
        layout_resumo.setSpacing(12)

        # stretch=1 pro cartão de resumo acompanhar a altura do
        # carrinho ao lado, em vez de ficar pequeno com um vão cinza
        # vazio embaixo — o conteúdo continua compacto e ancorado no
        # topo do card (ver stretch interno em _construir_cartao_resumo).
        layout_resumo.addWidget(self._construir_cartao_resumo(), stretch=1)
        layout_resumo.addWidget(self._construir_botao_pagar())

        corpo.addWidget(painel_resumo)

        layout.addLayout(corpo, stretch=1)

        layout.addWidget(self._construir_barra_atalhos())

        # ======================
        # ATALHOS DE TECLADO
        # ======================

        contexto = Qt.WidgetWithChildrenShortcut

        self.atalho_f1 = QShortcut(QKeySequence(self.atalhos["busca"]), self)
        self.atalho_f1.setContext(contexto)
        self.atalho_f1.activated.connect(self.abrir_busca)

        self.atalho_f4 = QShortcut(QKeySequence(self.atalhos["cadastro_rapido"]), self)
        self.atalho_f4.setContext(contexto)
        self.atalho_f4.activated.connect(self.abrir_novo_produto)

        self.atalho_esc = QShortcut(QKeySequence(self.atalhos["cancelar"]), self)
        self.atalho_esc.setContext(contexto)
        self.atalho_esc.activated.connect(self.cancelar_venda)

        # F2 (cliente) e F6 (desconto/acréscimo) não conflitam com
        # nenhum atalho existente e já têm uma ação óbvia associada —
        # F3 (pagar) continua tratado globalmente por PrincipalWindow.
        self.atalho_f2 = QShortcut(QKeySequence("F2"), self)
        self.atalho_f2.setContext(contexto)
        self.atalho_f2.activated.connect(self.abrir_selecionar_cliente)

        self.atalho_f6 = QShortcut(QKeySequence("F6"), self)
        self.atalho_f6.setContext(contexto)
        self.atalho_f6.activated.connect(self._alternar_bloco_ajuste)

        self.atalho_f7 = QShortcut(QKeySequence("F7"), self)
        self.atalho_f7.setContext(contexto)
        self.atalho_f7.activated.connect(self._abrir_ajuste_acrescimo)

        # Del / + / - / setas agem no item selecionado do cupom, tanto
        # com o foco no campo de codigo (vazio) quanto na propria lista
        self.campo_codigo.installEventFilter(self)
        self.tabela.installEventFilter(self)

        fade_in(self, duracao=200)

    def showEvent(self, event):
        super().showEvent(event)
        self.recarregar_atalhos()
        self.campo_codigo.setFocus()
        # as duas chamadas abaixo dependem do backend (rede) -- adiadas
        # pro próximo ciclo de eventos pra tela do PDV aparecer na hora
        # em vez de travar a troca de aba esperando a resposta.
        QTimer.singleShot(0, self.atualizar_indicador_caixa)
        QTimer.singleShot(0, self.atualizar_mais_vendidos)
        QTimer.singleShot(0, self._atualizar_contagem_suspensas)

    def _carregar_atalhos(self):
        salvo = preferencias_service.carregar(self._usuario_id, "pdv_atalhos", {})
        return {**ATALHOS_PADRAO, **(salvo or {})}

    def recarregar_atalhos(self):
        """Reflete na hora qualquer remapeamento feito em Configurações
        — chamado toda vez que a tela do PDV é reaberta, já que o
        widget nunca é recriado enquanto o app está de pé."""

        self.atalhos = self._carregar_atalhos()

        self.atalho_f1.setKey(QKeySequence(self.atalhos["busca"]))
        self.atalho_f4.setKey(QKeySequence(self.atalhos["cadastro_rapido"]))
        self.atalho_esc.setKey(QKeySequence(self.atalhos["cancelar"]))

        self.bt_buscar.setText(f"Buscar ({self.atalhos['busca']})")
        self.bt_adicionar.setText(f"Novo Produto ({self.atalhos['cadastro_rapido']})")

        self.lbl_atalho_busca_tecla.setText(self.atalhos["busca"])
        self.lbl_atalho_produto_tecla.setText(self.atalhos["cadastro_rapido"])

    # ==================================================
    # INDICADOR DE CAIXA ABERTO
    # ==================================================

    def atualizar_indicador_caixa(self):

        info = caixa_aberto()

        if not info:
            self.badge_caixa.setText("Caixa fechado")
            self.badge_caixa.setStyleSheet(f"""
                background: {tokens.ERRO_CLARO}; color: {tokens.ERRO_HOVER};
                border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
                font-weight: 600; padding: 3px 10px;
            """)
            return

        if info.get("vencido"):
            self.badge_caixa.setText("Caixa aberto há +24h — feche o caixa")
            self.badge_caixa.setStyleSheet(f"""
                background: {tokens.ERRO_CLARO}; color: {tokens.ERRO_HOVER};
                border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
                font-weight: 600; padding: 3px 10px;
            """)
            return

        abertura = _parse_data(info.get("data_abertura"))
        hora_texto = abertura.strftime("%H:%M") if abertura else "—"

        self.badge_caixa.setText(f"Caixa aberto às {hora_texto}")
        self.badge_caixa.setStyleSheet(f"""
            background: {tokens.SUCESSO_CLARO}; color: {tokens.SECUNDARIA_HOVER};
            border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
            font-weight: 600; padding: 3px 10px;
        """)

    # ==================================================
    # CÓDIGO DE BARRAS (campo gigante)
    # ==================================================

    def processar_codigo(self):

        codigo = self.campo_codigo.text().strip()

        if not codigo:
            return

        quantidade, codigo = _separar_multiplicador(codigo)

        if not codigo:
            return  # so' "3*" -- espera o codigo

        produto = buscar_produto(codigo)

        if produto is None:
            self._mostrar_status_busca(f"Produto não encontrado: {codigo}", erro=True)
            self.campo_codigo.selectAll()
            return

        if not self.adicionar_produto_ao_carrinho(produto, quantidade):
            self.campo_codigo.selectAll()
            return

        self.campo_codigo.clear()

    def _atualizar_multiplicador(self, texto):

        quantidade, _ = _separar_multiplicador(texto.strip())
        tem_multiplicador = "*" in texto and quantidade > 1

        self.lbl_multiplicador.setText(f"× {quantidade}")
        self.lbl_multiplicador.setVisible(tem_multiplicador)

    def _mostrar_status_busca(self, texto, erro):

        cor = tokens.ERRO if erro else tokens.SECUNDARIA
        self.lbl_status_busca.setStyleSheet(f"""
            background:transparent; color:{cor};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        self.lbl_status_busca.setText(texto)
        self.lbl_status_busca.setVisible(True)

        QTimer.singleShot(
            2500,
            lambda: (
                (self.lbl_status_busca.setText(""), self.lbl_status_busca.setVisible(False))
                if self.lbl_status_busca.text() == texto else None
            ),
        )

    # ==================================================
    # BUSCAR PRODUTO (F1) - abre o modal de pesquisa
    # ==================================================

    def abrir_busca(self):

        dialog = BuscarProdutoDialog(self)
        dialog.produto_selecionado.connect(
            self.adicionar_produto_ao_carrinho
        )
        dialog.exec()

    def adicionar_produto_ao_carrinho(self, produto, quantidade):

        item_existente = next(
            (item for item in self.itens if item["id"] == produto["id"]),
            None,
        )

        no_carrinho = item_existente["quantidade"] if item_existente else 0
        estoque = produto.get("estoque")

        # estoque None = dado nao veio junto (nao deveria acontecer,
        # mas nao trava a venda por causa disso - so pula a checagem)
        if estoque is not None and no_carrinho + quantidade > estoque:

            if estoque <= 0:
                mensagem = f"{produto['nome']} está sem estoque disponível."
            elif no_carrinho > 0:
                mensagem = (
                    f"Estoque insuficiente de {produto['nome']} — "
                    f"disponível: {estoque}, já no carrinho: {no_carrinho}."
                )
            else:
                mensagem = (
                    f"Estoque insuficiente de {produto['nome']} — "
                    f"disponível: {estoque}."
                )

            self._mostrar_status_busca(mensagem, erro=True)
            return False

        if item_existente:
            item_existente["quantidade"] += quantidade
        else:
            self.itens.append(
                {
                    "id": produto["id"],
                    "codigo": produto["codigo"],
                    "nome": produto["nome"],
                    "preco": float(produto["preco"]),
                    "quantidade": quantidade,
                    "estoque": estoque,
                    "tem_foto": produto.get("tem_foto", False),
                }
            )

        self._id_ultimo_item = produto["id"]
        self.atualizar_tabela()
        return True

    # ==================================================
    # NOVO PRODUTO (F4) - cadastro completo sem sair do PDV
    # ==================================================

    def abrir_novo_produto(self):

        dialog = CadastroProdutoWindow()

        if dialog.exec() != QDialog.Accepted:
            return

        response = cadastrar_produto(dialog.dados)

        if response.status_code != 201:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        produto_criado = response.json()

        # a resposta do cadastro vem no formato "cru" (preco_venda) --
        # o carrinho espera o formato do PDV (preco), entao rebusca
        # pelo codigo pra pegar exatamente o mesmo shape que o F1/scanner usa
        codigo = (
            produto_criado.get("codigo_barras")
            or produto_criado.get("codigo")
        )

        produto = buscar_produto(codigo)

        if produto is None:
            return

        self.adicionar_produto_ao_carrinho(produto, 1)
        self._mostrar_status_busca(
            f"Produto cadastrado e adicionado: {produto['nome']}",
            erro=False,
        )

    # ==================================================
    # CLIENTE (opcional, vale pra qualquer forma de pagamento)
    # ==================================================

    def abrir_selecionar_cliente(self):

        dialogo = SelecionarClienteDialog(self)
        dialogo.cliente_selecionado.connect(self.definir_cliente)
        dialogo.exec()

    def definir_cliente(self, cliente):

        self.cliente_id = cliente["id"]
        self.cliente_nome = cliente["nome"]

        self.lbl_cliente.setText(cliente["nome"])
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        self.bt_limpar_cliente.setVisible(True)

    def limpar_cliente(self):

        self.cliente_id = None
        self.cliente_nome = None

        self.lbl_cliente.setText("Nenhum cliente selecionado")
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        self.bt_limpar_cliente.setVisible(False)

    # ==================================================
    # DESCONTO / ACRÉSCIMO
    # ==================================================

    def _alternar_bloco_ajuste(self):
        self.bloco_ajuste.setVisible(not self.bloco_ajuste.isVisible())
        if self.bloco_ajuste.isVisible():
            self.campo_desconto.setFocus()
            self.campo_desconto.selectAll()

    def _abrir_ajuste_acrescimo(self):
        # sempre abre (nao alterna) -- F7 e' "eu quero mexer no
        # acrescimo agora", nao "esconde se ja tiver aberto"
        self.bloco_ajuste.setVisible(True)
        self.campo_acrescimo.setFocus()
        self.campo_acrescimo.selectAll()

    # ==================================================
    # TECLADO NO CUPOM (Del / + / - / setas)
    # ==================================================

    def eventFilter(self, origem, evento):

        if evento.type() != QEvent.KeyPress or not self.itens:
            return super().eventFilter(origem, evento)

        tecla = evento.key()
        no_campo = origem is self.campo_codigo
        campo_vazio = not self.campo_codigo.text().strip()

        if tecla in (Qt.Key_Up, Qt.Key_Down):
            linha = self._linha_selecionada()
            passo = -1 if tecla == Qt.Key_Up else 1
            nova = max(0, min(len(self.itens) - 1, linha + passo))
            self.tabela.selectRow(nova)
            self._id_ultimo_item = self.itens[nova]["id"]
            self._atualizar_ultimo_item()
            return True

        # no campo de codigo, Del/+/- so' valem com o campo vazio --
        # com texto, sao edicao normal do que esta' sendo digitado
        if no_campo and not campo_vazio:
            return super().eventFilter(origem, evento)

        if tecla == Qt.Key_Delete:
            self.remover_item(self._linha_selecionada())
            return True

        if tecla == Qt.Key_Plus:
            self.alterar_quantidade(self._linha_selecionada(), 1)
            return True

        if tecla == Qt.Key_Minus:
            self.alterar_quantidade(self._linha_selecionada(), -1)
            return True

        return super().eventFilter(origem, evento)

    # ==================================================
    # CANCELAR VENDA
    # ==================================================

    def cancelar_venda(self):

        # carrinho vazio mas com troca pendente: cancelar também precisa
        # tirar o crédito, senão ele iria pra venda do próximo cliente
        if not self.itens and not self.credito_troca:
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

        if self.credito_troca > 0:
            QMessageBox.information(
                self,
                "Troca",
                "A devolução já foi registrada. Como a cliente não levou "
                f"outra peça, devolva {formatar_moeda(self.credito_troca)} "
                "em dinheiro para ela.",
            )

        self.limpar_venda()

    def iniciar_troca(self, credito, cliente=None):
        """Chamado pela tela de Vendas depois de registrar a devolução
        da troca: o valor devolvido vira crédito desta venda (entra
        como dinheiro já recebido no pagamento)."""

        if self.itens:
            self.limpar_venda()

        self.credito_troca = round(credito, 2)
        self.badge_troca.setText(f"Troca: crédito de {formatar_moeda(credito)}")
        self.badge_troca.setVisible(True)

        if cliente and cliente.get("id"):
            self.definir_cliente(cliente)

        self.campo_codigo.setFocus()

    def limpar_venda(self):

        self.credito_troca = 0.0
        self.badge_troca.setVisible(False)

        self._chave_venda = None
        self.itens.clear()
        self._id_ultimo_item = None
        self._atualizar_ultimo_item()

        self.tabela.setRowCount(0)
        self.pilha_carrinho.setCurrentWidget(self.pilha_carrinho.widget(0))

        self.limpar_cliente()

        self.campo_desconto.setText("")
        self.campo_acrescimo.setText("")
        self.bloco_ajuste.setVisible(False)

        self.lbl_itens_valor.setText("0")
        self.lbl_itens_tabela.setText("0 itens")
        self.lbl_subtotal_valor.setText(formatar_moeda(0))
        self.lbl_desconto_valor.setText(formatar_moeda(0))
        self.lbl_acrescimo_valor.setText(formatar_moeda(0))
        self.lbl_desconto_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)
        self.lbl_acrescimo_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)

        self.total.setText("R$ 0,00")

        self.campo_codigo.setFocus()

    def _ignorar_erro(self, erro):
        pass

    # ==================================================
    # FINALIZAR VENDA (PAGAR - F3)
    # ==================================================

    def finalizar_venda(self):

        # Trava de reentrância: bloqueia clique duplo no botão e F3
        # repetido (o atalho global em principal.py chama este mesmo
        # método) enquanto uma venda já está em andamento -- sem isso,
        # um duplo clique durante a resposta lenta do servidor (ex.:
        # modo Terminal, multi-dispositivo) podia disparar duas vendas
        # pro mesmo carrinho.
        if self._finalizando_venda:
            return

        if not self.itens:
            QMessageBox.warning(
                self,
                "Aviso",
                "Nenhum produto foi adicionado."
            )

            return

        total = self._recalcular_totais()

        if self._total_bruto < 0:
            QMessageBox.warning(
                self,
                "Aviso",
                "O desconto não pode ser maior que o total da venda."
            )
            return

        # PagamentoWindow e' so' local (forma de pagamento, troco...),
        # sem chamada de rede -- fica sincrono/modal mesmo, so' a
        # submissao da venda em si (dali pra baixo) vai pra thread.
        tela = PagamentoWindow(
            total,
            self.itens,
            cliente_id=self.cliente_id,
            cliente_nome=self.cliente_nome,
            desconto=self.desconto_valor,
            acrescimo=self.acrescimo_valor,
            credito_troca=self.credito_troca,
        )

        if tela.exec() != QDialog.Accepted:
            return

        # sem UI otimista aqui de proposito: venda envolve dinheiro e
        # baixa de estoque de verdade no servidor, nao tem "desfazer"
        # seguro no cliente -- a tela so' mostra "venda concluida"
        # depois que o 201 realmente voltar.
        self._finalizando_venda = True
        self.bt_pagar.setEnabled(False)
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        self._venda_pagamento_tela = tela
        self._venda_total_em_andamento = total

        desconto_liquido = self.desconto_valor - self.acrescimo_valor

        # Mesma chave em todo reenvio deste carrinho: se a resposta se
        # perder (timeout/rede) e o caixa clicar de novo, o backend
        # devolve a venda ja gravada em vez de vender duas vezes. So'
        # zera quando a venda deu certo ou o servidor RECUSOU de vez
        # (ver _ao_venda_sucesso).
        if self._chave_venda is None:
            self._chave_venda = uuid.uuid4().hex

        rodar_em_thread(
            self,
            enviar_venda,
            chave_idempotencia=self._chave_venda,
            itens=self.itens,
            forma_pagamento=tela.forma_pagamento,
            cliente_id=tela.cliente_id,
            desconto=desconto_liquido,
            observacao=tela.observacao.text().strip() or None,
            data_vencimento=None,
            forma_pagamento_2=tela.forma_pagamento_2,
            valor_forma_2=(
                tela.valor_forma_2 if tela.forma_pagamento_2 else None
            ),
            ao_sucesso=self._ao_venda_sucesso,
            ao_erro=self._ao_venda_erro,
            ao_finalizar=self._ao_venda_finalizada,
        )

    def _ao_venda_sucesso(self, response):

        tela = self._venda_pagamento_tela
        total = self._venda_total_em_andamento

        if response.status_code == 201:

            venda_criada = response.json()

            concluida = VendaConcluidaDialog(
                venda_criada["id"],
                total,
                self.itens,
                tela.forma_pagamento,
                cliente_nome=tela.cliente_nome,
                forma_pagamento_2=tela.forma_pagamento_2,
                valor_forma_2=tela.valor_forma_2,
                parent=self,
            )
            concluida.exec()

            sobra_troca = round(self.credito_troca - total, 2)
            if sobra_troca > 0:
                QMessageBox.information(
                    self,
                    "Troca",
                    f"A peça nova saiu mais barata. Devolva R$ "
                    f"{formatar_moeda(sobra_troca).replace('R$', '').strip()} "
                    "em dinheiro para a cliente.",
                )

            self.limpar_venda()

        else:

            # o servidor respondeu e recusou (estoque, preco, caixa
            # fechado...): nada foi gravado, a proxima tentativa (talvez
            # com o carrinho corrigido) e' uma venda nova
            self._chave_venda = None

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

    def _ao_venda_erro(self, erro):

        # sem resposta do servidor (timeout, rede): a venda PODE ter
        # sido gravada. A chave continua a mesma, entao tentar de novo
        # e' seguro -- nao vende duas vezes.
        QMessageBox.critical(
            self,
            "Erro",
            f"{erro}\n\nSe a venda já tiver sido registrada, tentar de "
            "novo não vai duplicar."
        )

    def _ao_venda_finalizada(self):

        self._finalizando_venda = False
        self.bt_pagar.setEnabled(True)
        QApplication.restoreOverrideCursor()
        self._venda_pagamento_tela = None
        self._venda_total_em_andamento = None
