import unicodedata

from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMessageBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.cliente_service import listar_clientes
from services.movimento_fiado_service import listar_movimentos
from services import cliente_analise
from services.worker import rodar_em_thread, em_paralelo
from telas.cadastro_cliente import CadastroClienteDialog
from design import tokens
from design.icons import icone
from design.widgets import (
    Avatar, Badge, BotaoPrimario, BotaoSucesso, CampoTexto, DialogoPadrao,
)
from utils.formatacao import formatar_moeda


def _sem_acento(texto):
    """'José' -> 'jose': a busca acha com ou sem acento."""
    normal = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in normal if not unicodedata.combining(c))


def _so_digitos(texto):
    return "".join(c for c in str(texto or "") if c.isdigit())


def _carregar_clientes():
    """Roda na worker thread -- clientes + movimentos de fiado UMA vez
    (antes cada letra digitada buscava a lista inteira de novo). O
    saldo devedor vem dos movimentos, mesma regra da tela de Clientes
    (services/cliente_analise.py)."""

    clientes, movimentos = em_paralelo(
        (listar_clientes,),
        (listar_movimentos,),
    )

    por_cliente = {}
    for mov in movimentos or []:
        if mov.get("cliente_id") is not None:
            por_cliente.setdefault(mov["cliente_id"], []).append(mov)

    ativos = []
    for cliente in clientes or []:
        if not cliente.get("ativo", True):
            continue
        agr = cliente_analise.calcular_agregados(cliente, por_cliente.get(cliente["id"], []))
        ativos.append({
            **cliente,
            "_agr": agr,
            "_busca_texto": _sem_acento(
                f"{cliente.get('nome') or ''} {cliente.get('email') or ''} {cliente.get('cidade') or ''}"
            ),
            "_busca_digitos": _so_digitos(
                f"{cliente.get('telefone') or ''} {cliente.get('cpf_cnpj') or ''}"
            ),
        })

    return ativos


def situacao_fiado(cliente):
    """(texto do selo, variante, disponível ou None) do crédito do
    cliente -- o que o caixa precisa saber antes de vender fiado."""

    agr = cliente.get("_agr") or {}
    saldo = float(agr.get("saldo_devedor", 0) or 0)
    limite = float(cliente.get("limite_credito") or 0)
    disponivel = (limite - saldo) if limite > 0 else None

    if cliente.get("negativado"):
        return "NEGATIVADO · não vender", "erro", None

    if agr and cliente_analise.eh_inadimplente(agr):
        return f"Atrasado · {agr.get('dias_em_atraso')} dias", "erro", disponivel
    if limite > 0 and saldo >= limite - 0.009:
        return "Limite estourado", "erro", disponivel
    if saldo <= 0.009:
        return "Em dia", "sucesso", disponivel
    if limite > 0 and saldo / limite >= 0.85:
        return "Perto do limite", "alerta", disponivel
    return "Fiado em aberto", "info", disponivel


class ItemResultadoCliente(QWidget):

    def __init__(self, cliente):

        super().__init__()
        self.setStyleSheet("background:transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 14, 10)
        layout.setSpacing(12)

        layout.addWidget(Avatar(cliente.get("nome") or "?", 40))

        col_texto = QVBoxLayout()
        col_texto.setSpacing(2)

        nome = QLabel(cliente.get("nome") or "")
        nome.setStyleSheet(f"""
            background:transparent; font-weight:700; font-size:{tokens.TAMANHO_MD}px;
            color:{tokens.TEXTO};
        """)

        detalhes = "  ·  ".join(filter(None, [
            cliente.get("telefone"), cliente.get("cpf_cnpj"), cliente.get("cidade"),
        ])) or "Sem contato cadastrado"
        subtitulo = QLabel(detalhes)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px; color:{tokens.TEXTO_SECUNDARIO};
        """)

        linha_nome = QHBoxLayout()
        linha_nome.setSpacing(8)
        linha_nome.addWidget(nome)
        selo = cliente_analise.selo_pagador(cliente.get("_agr"))
        if selo:
            linha_nome.addWidget(Badge(*selo))
        linha_nome.addStretch()

        col_texto.addLayout(linha_nome)
        col_texto.addWidget(subtitulo)
        layout.addLayout(col_texto, 1)

        # ---- fiado: selo + saldo, e embaixo limite/disponível ----
        texto_selo, variante, disponivel = situacao_fiado(cliente)
        saldo = float((cliente.get("_agr") or {}).get("saldo_devedor", 0) or 0)

        col_fiado = QVBoxLayout()
        col_fiado.setSpacing(3)

        linha_saldo = QHBoxLayout()
        linha_saldo.setSpacing(8)
        linha_saldo.addStretch()
        linha_saldo.addWidget(Badge(texto_selo, variante))
        if saldo > 0.009:
            cor_saldo = tokens.ERRO if variante == "erro" else tokens.TEXTO
            texto_saldo = formatar_moeda(saldo)
        else:
            cor_saldo = tokens.TEXTO_TERCIARIO
            texto_saldo = "Sem dívida"
        lbl_saldo = QLabel(texto_saldo)
        lbl_saldo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_MD}px; font-weight:800; color:{cor_saldo};
        """)
        linha_saldo.addWidget(lbl_saldo)
        col_fiado.addLayout(linha_saldo)

        limite = formatar_moeda(cliente.get("limite_credito") or 0)
        if disponivel is None:
            texto_limite = "Sem limite de crédito definido"
        elif disponivel <= 0:
            texto_limite = f"Limite {limite}  ·  nada disponível"
        else:
            texto_limite = f"Limite {limite}  ·  disponível {formatar_moeda(disponivel)}"
        lbl_limite = QLabel(texto_limite)
        lbl_limite.setAlignment(Qt.AlignRight)
        lbl_limite.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px; color:{tokens.TEXTO_TERCIARIO};
        """)
        col_fiado.addWidget(lbl_limite)

        layout.addLayout(col_fiado)


MAX_RESULTADOS = 30


class SelecionarClienteDialog(DialogoPadrao):
    """Busca de cliente do PDV (F2) e do crediário no pagamento. Mostra
    a situação do fiado de cada um -- quem está devendo, atrasado ou sem
    limite -- antes do caixa escolher."""

    cliente_selecionado = Signal(dict)

    def __init__(self, parent=None):

        super().__init__(
            "Selecionar cliente", "Busque por nome, telefone ou CPF",
            "users", largura=DialogoPadrao.MEDIO, parent=parent,
        )
        self.resize(DialogoPadrao.MEDIO, 640)

        self._clientes_ativos = []
        self._carregado = False

        # ---- busca + novo ----
        linha = QHBoxLayout()
        linha.setSpacing(10)

        self.busca = CampoTexto("Digite o nome, WhatsApp ou CPF do cliente...")
        self.busca.setMinimumHeight(48)
        self.busca.addAction(
            icone("search", cor=tokens.TEXTO_TERCIARIO, tamanho=16), QLineEdit.LeadingPosition
        )
        self.busca.installEventFilter(self)
        # filtra na hora: a lista já está na memória
        self.busca.textChanged.connect(self.executar_busca)

        bt_novo = BotaoSucesso("Novo cliente", icone_nome="plus")
        bt_novo.setAutoDefault(False)
        bt_novo.setMinimumHeight(48)
        bt_novo.setToolTip("Ctrl+N")
        bt_novo.clicked.connect(self.novo_cliente)

        linha.addWidget(self.busca, 1)
        linha.addWidget(bt_novo)
        self.corpo.addLayout(linha)

        self.lbl_contador = QLabel("CARREGANDO CLIENTES...")
        self.lbl_contador.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px; font-weight:800;
            color:{tokens.TEXTO_SECUNDARIO}; letter-spacing:0.5px;
        """)
        self.corpo.addWidget(self.lbl_contador)

        # ---- lista ----
        self.lista = QListWidget()
        self.lista.setStyleSheet(f"""
            QListWidget {{
                border:1.5px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_MD}px;
                background:{tokens.CARD}; outline:none;
            }}
            QListWidget::item {{ border-bottom:1px solid {tokens.BORDA}; }}
            QListWidget::item:hover {{ background:{tokens.FUNDO}; }}
            QListWidget::item:selected {{
                background:{tokens.PRIMARIA_CLARA};
                border-left:4px solid {tokens.PRIMARIA};
            }}
        """)
        self.lista.itemDoubleClicked.connect(self.selecionar_atual)
        self.lista.currentRowChanged.connect(lambda _l: self._atualizar_botao())
        self.corpo.addWidget(self.lista, 1)

        self.lbl_vazio = QLabel("")
        self.lbl_vazio.setAlignment(Qt.AlignCenter)
        self.lbl_vazio.setWordWrap(True)
        self.lbl_vazio.setStyleSheet(f"""
            background:{tokens.FUNDO}; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_BASE}px; border-radius:{tokens.RADIUS_MD}px; padding:30px;
        """)
        self.lbl_vazio.setVisible(False)
        self.corpo.addWidget(self.lbl_vazio, 1)

        # ---- rodapé ----
        dica = QLabel("↑↓ navega  ·  Enter seleciona  ·  Ctrl+N novo cliente  ·  Esc fecha")
        dica.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px; color:{tokens.TEXTO_TERCIARIO};
        """)
        self.rodape.addWidget(dica)

        self.bt_selecionar = BotaoPrimario("Selecionar", icone_nome="check")
        self.bt_selecionar.setAutoDefault(False)
        self.bt_selecionar.clicked.connect(self.selecionar_atual)
        self.definir_botoes(self.bt_selecionar)
        self.bt_selecionar.setMinimumWidth(160)
        self.bt_cancelar.setMinimumWidth(120)

        atalho_novo = QShortcut(QKeySequence("Ctrl+N"), self)
        atalho_novo.activated.connect(self.novo_cliente)

        self._atualizar_botao()
        self.busca.setFocus()

        rodar_em_thread(
            self,
            _carregar_clientes,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_busca_erro,
        )

    # ==================================================

    def _ao_carregar_sucesso(self, ativos):
        self._clientes_ativos = ativos
        self._carregado = True
        self.executar_busca()

    def executar_busca(self, *_):

        if not self._carregado:
            return

        termo = _sem_acento(self.busca.text().strip())
        digitos = _so_digitos(termo)

        if termo:
            clientes = [
                c for c in self._clientes_ativos
                if termo in c["_busca_texto"]
                or (len(digitos) >= 3 and digitos in c["_busca_digitos"])
            ]
            # nome que COMEÇA com o que foi digitado vem primeiro
            clientes.sort(key=lambda c: (
                not c["_busca_texto"].startswith(termo), c["_busca_texto"]
            ))
        else:
            # sem busca: quem movimentou por último aparece primeiro (é
            # quem costuma voltar), depois o resto em ordem alfabética
            def chave(c):
                ultima = (c.get("_agr") or {}).get("ultima_movimentacao")
                return (ultima is None, -(ultima.timestamp() if ultima else 0), c["_busca_texto"])
            clientes = sorted(self._clientes_ativos, key=chave)

        self._mostrar(clientes, termo)

    def _mostrar(self, clientes, termo):

        self.lista.clear()

        # cada linha e' um widget caro (400 levavam ~2,5 s a cada letra);
        # quem nao esta' entre os primeiros, o caixa acha digitando mais
        for cliente in clientes[:MAX_RESULTADOS]:
            widget = ItemResultadoCliente(cliente)
            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.UserRole, cliente)
            self.lista.addItem(item)
            self.lista.setItemWidget(item, widget)

        if self.lista.count() > 0:
            self.lista.setCurrentRow(0)

        total = len(self._clientes_ativos)
        if termo:
            self.lbl_contador.setText(f"{len(clientes)} DE {total} CLIENTES")
        else:
            self.lbl_contador.setText(f"{total} CLIENTES  ·  QUEM MOVIMENTOU POR ÚLTIMO PRIMEIRO")
        if len(clientes) > MAX_RESULTADOS:
            self.lbl_contador.setText(
                self.lbl_contador.text() + f"  ·  MOSTRANDO {MAX_RESULTADOS}, DIGITE MAIS PRA ACHAR"
            )

        vazio = self.lista.count() == 0
        self.lista.setVisible(not vazio)
        self.lbl_vazio.setVisible(vazio)

        if vazio:
            if termo:
                self.lbl_vazio.setText(
                    f'Nenhum cliente encontrado para "{self.busca.text().strip()}".\n\n'
                    "Confira a grafia ou cadastre com Ctrl+N."
                )
            else:
                self.lbl_vazio.setText(
                    "Nenhum cliente cadastrado ainda.\n"
                    "Cadastre um novo cliente pra começar o fiado dele."
                )

        self._atualizar_botao()

    def _ao_busca_erro(self, erro):
        self.lista.clear()
        self.lista.setVisible(False)
        self.lbl_vazio.setText(f"Não foi possível buscar clientes.\n{erro}")
        self.lbl_vazio.setVisible(True)
        self.lbl_contador.setText("")
        self._atualizar_botao()

    def _atualizar_botao(self):
        self.bt_selecionar.setEnabled(self.lista.currentItem() is not None)

    # ==================================================

    def eventFilter(self, obj, event):

        if obj is self.busca and event.type() == QEvent.KeyPress:

            if event.key() == Qt.Key_Down:
                self._mover_selecao(1)
                return True

            if event.key() == Qt.Key_Up:
                self._mover_selecao(-1)
                return True

            if event.key() in (Qt.Key_PageDown, Qt.Key_PageUp):
                self._mover_selecao(5 if event.key() == Qt.Key_PageDown else -5)
                return True

            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.selecionar_atual()
                return True

            if event.key() == Qt.Key_Escape:
                self.reject()
                return True

        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        # Enter com o foco na lista também seleciona
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and self.lista.hasFocus():
            self.selecionar_atual()
            return
        super().keyPressEvent(event)

    def _mover_selecao(self, delta):

        if self.lista.count() == 0:
            return

        linha = self.lista.currentRow()
        nova = max(0, min(self.lista.count() - 1, linha + delta))

        self.lista.setCurrentRow(nova)
        self.lista.scrollToItem(self.lista.currentItem())

    def selecionar_atual(self, *_args):

        item = self.lista.currentItem()

        if item is None:
            return

        # devolve o cliente sem os campos internos da busca
        cliente = {k: v for k, v in item.data(Qt.UserRole).items() if not k.startswith("_")}

        # negativado nao compra nada (o backend tambem recusa a venda)
        if cliente.get("negativado"):
            QMessageBox.warning(
                self, "Cliente negativado",
                f"{cliente.get('nome')} está NEGATIVADO: não é possível vender para "
                "este cliente. Só um administrador pode desbloquear, na ficha dele.",
            )
            return

        self.cliente_selecionado.emit(cliente)

        self.accept()

    # ==================================================

    def novo_cliente(self):

        dialogo = CadastroClienteDialog(parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        if not dialogo.cliente_salvo:
            return

        self.cliente_selecionado.emit(dialogo.cliente_salvo)

        self.accept()
