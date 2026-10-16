import json

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QFileDialog,
    QScrollArea,
    QMessageBox,
)

from services import api
from services.movimento_fiado_service import (
    saldo_cliente,
)
from services.cliente_service import (
    obter_foto_cliente,
    negativar_cliente,
    desbloquear_cliente,
)
from services import cliente_analise
from services.worker import rodar_em_thread
from design import tokens
from design.icons import icone
from utils.formatacao import formatar_moeda
from design.widgets import (
    Avatar,
    Badge,
    BotaoPerigo,
    BotaoPrimario,
    BotaoSecundario,
    BotaoSucesso,
    CardKPI,
    pedir_texto,
    SecaoCard,
)
from telas.ficha_cliente.comum import _buscar_dados_ficha_cliente, _pixmap_circular
from telas.ficha_cliente.extrato import ExtratoMixin
from telas.ficha_cliente.historico import HistoricoMixin
from telas.ficha_cliente.lancar_fiado import LancarFiadoDialog
from telas.ficha_cliente.observacoes import ObservacoesMixin
from telas.ficha_cliente.registrar_pagamento import RegistrarPagamentoDialog
from telas.ficha_cliente.whatsapp import WhatsAppMixin


class FichaClienteDialog(WhatsAppMixin, ObservacoesMixin, HistoricoMixin, ExtratoMixin, QDialog):

    _TIMELINE_PAGINA = 30  # scroll incremental: 30 lançamentos por vez

    def __init__(self, cliente, parent=None):

        super().__init__(parent)

        self.cliente = cliente
        self._vendas_por_id = {}
        self._nomes_produto = {}
        self._movimentos = []
        self._carregando = False

        self._filtro_timeline = "TODOS"
        self._busca_timeline = ""
        self._timeline_qtd_exibida = self._TIMELINE_PAGINA

        self.setWindowTitle(f"Ficha - {cliente['nome']}")
        self._dimensionar_e_centralizar()
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        raiz.addWidget(self._construir_cabecalho())

        corpo = QHBoxLayout()
        corpo.setContentsMargins(28, 4, 28, 12)
        corpo.setSpacing(16)

        coluna_esquerda = QVBoxLayout()
        coluna_esquerda.setSpacing(14)

        coluna_esquerda.addWidget(self._construir_linha_cards())
        coluna_esquerda.addLayout(self._construir_botoes_acao())
        coluna_esquerda.addLayout(self._construir_filtros_timeline())
        coluna_esquerda.addWidget(self._construir_timeline(), stretch=1)

        corpo.addLayout(coluna_esquerda, stretch=2)
        corpo.addWidget(self._construir_painel_lateral())

        raiz.addLayout(corpo, stretch=1)
        raiz.addWidget(self._construir_rodape())

        # sem isso o foco inicial cai no botão WhatsApp (o primeiro da
        # tela), que abre com a moldura de foco desenhada
        self.campo_busca_timeline.setFocus()

        self.carregar()

    def _dimensionar_e_centralizar(self):
        """Tamanho da janela calculado a partir da tela de verdade (90%
        da área útil, sem contar a barra de tarefas), nunca um valor
        fixo no código -- funciona igual em qualquer resolução (de
        1366x768 até 4K), sempre dentro da área disponível do Windows,
        e já abre centralizada."""

        tela = QApplication.primaryScreen().availableGeometry()

        largura = int(tela.width() * 0.9)
        altura = int(tela.height() * 0.9)

        self.resize(largura, altura)
        self.move(
            tela.x() + (tela.width() - largura) // 2,
            tela.y() + (tela.height() - altura) // 2,
        )

    # ======================================
    # CONSTRUÇÃO DA INTERFACE
    # ======================================

    def _construir_cabecalho(self):
        """Cabeçalho claro, no mesmo padrão das outras telas (antes era
        uma faixa escura que só existia aqui): avatar, nome com os selos
        de situação e pontuação, telefone e "cliente desde" embaixo, e
        os botões de contato + Editar na ponta direita."""

        cabecalho = QFrame()
        cabecalho.setStyleSheet("background:transparent;")

        layout = QHBoxLayout(cabecalho)
        layout.setContentsMargins(28, 20, 28, 16)
        layout.setSpacing(14)

        self.avatar = Avatar(self.cliente.get("nome", ""), tamanho=48)
        layout.addWidget(self.avatar)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(2)

        linha_nome = QHBoxLayout()
        linha_nome.setSpacing(10)

        self.lbl_titulo = QLabel(self.cliente["nome"])
        self.lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)

        self.badge_ativo = Badge("Ativo", "sucesso")

        # selo de pontuacao (Cliente Ocasional/Frequente/Excelente/...)
        # -- comeca vazio, so' ganha texto/cor em _atualizar_stats
        # (precisa do historico de movimentos, que ainda nao foi
        # buscado nesse ponto da construcao)
        self.badge_pontuacao = Badge("", "info")
        self.badge_pontuacao.setVisible(False)

        linha_nome.addWidget(self.lbl_titulo)
        linha_nome.addWidget(self.badge_ativo, 0, Qt.AlignVCenter)
        linha_nome.addWidget(self.badge_pontuacao, 0, Qt.AlignVCenter)
        self.badge_negativado = Badge("NEGATIVADO · não vender", "erro")
        linha_nome.addWidget(self.badge_negativado, 0, Qt.AlignVCenter)
        linha_nome.addStretch()

        self.lbl_subtitulo = QLabel()
        self.lbl_subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        col_texto.addLayout(linha_nome)
        col_texto.addWidget(self.lbl_subtitulo)

        layout.addLayout(col_texto, stretch=1)

        linha_contato = QHBoxLayout()
        linha_contato.setSpacing(8)

        self.bt_whatsapp = self._botao_contato("WhatsApp", None, "message-circle")
        self.menu_whatsapp = self._construir_menu_whatsapp()
        self.bt_whatsapp.setMenu(self.menu_whatsapp)

        self.bt_ligar = self._botao_contato("Ligar", self.abrir_ligacao)
        self.bt_email = self._botao_contato("E-mail", self.abrir_email, "mail")

        linha_contato.addWidget(self.bt_whatsapp)
        linha_contato.addWidget(self.bt_ligar)
        linha_contato.addWidget(self.bt_email)
        linha_contato.addSpacing(6)

        self.bt_editar_cabecalho = BotaoPrimario("Editar Cliente", icone_nome="edit-2")
        self.bt_editar_cabecalho.setAutoDefault(False)
        self.bt_editar_cabecalho.clicked.connect(self.editar_cliente)
        linha_contato.addWidget(self.bt_editar_cabecalho)

        # so' admin negativa/desbloqueia (o backend tambem barra)
        self.bt_negativar = BotaoPerigo("Negativar", icone_nome="lock")
        self.bt_negativar.setAutoDefault(False)
        self.bt_negativar.clicked.connect(self._alternar_negativado)
        self.bt_negativar.setVisible(api.usuario_e_admin())
        linha_contato.addWidget(self.bt_negativar)

        layout.addLayout(linha_contato)

        self._atualizar_cabecalho(self.cliente)
        self._atualizar_avatar(self.cliente)

        return cabecalho

    def _construir_linha_cards(self):
        """4 números grandes numa linha (CardKPI, igual Clientes e
        Contas a Pagar) no lugar dos 10 mini-cards com rótulo de 8px.
        O que sobrou dos mini-cards virou legenda (limite, ticket médio,
        último pagamento) ou foi pro painel Detalhes ao lado. O aviso de
        situação só aparece quando há algo a avisar (atraso, limite)."""

        container = QFrame()
        container.setStyleSheet("background:transparent;")

        layout_externo = QVBoxLayout(container)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        layout_externo.setSpacing(10)

        grade = QGridLayout()
        grade.setSpacing(12)

        self.kpi_saldo = CardKPI("Saldo devedor", "wallet", tokens.PRIMARIA, destaque=True)
        self.kpi_comprado = CardKPI("Total comprado", "shopping-cart", tokens.PRIMARIA)
        self.kpi_pago = CardKPI("Total pago", "check", tokens.SECUNDARIA)
        self.kpi_ultima_compra = CardKPI("Última compra", "calendar", tokens.ALERTA)

        for coluna, card in enumerate((
            self.kpi_saldo, self.kpi_comprado, self.kpi_pago, self.kpi_ultima_compra,
        )):
            grade.addWidget(card, 0, coluna)
            grade.setColumnStretch(coluna, 1)

        layout_externo.addLayout(grade)

        self.lbl_aviso_status = QLabel("")
        self.lbl_aviso_status.setWordWrap(True)
        self.lbl_aviso_status.hide()
        layout_externo.addWidget(self.lbl_aviso_status)

        return container

    def _construir_botoes_acao(self):
        """Uma linha só: as ações do fiado à esquerda (lançar, receber,
        pagamento) e as de documento à direita (extrato, CSV)."""

        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.bt_lancar_fiado = BotaoPerigo("Lançar Fiado", icone_nome="plus")
        self.bt_lancar_fiado.setAutoDefault(False)
        self.bt_lancar_fiado.clicked.connect(self.lancar_fiado)

        self.bt_pagar = BotaoSucesso("Registrar Pagamento", icone_nome="check")
        self.bt_pagar.setAutoDefault(False)
        self.bt_pagar.clicked.connect(self.registrar_pagamento)

        self.bt_extrato = BotaoSecundario("Imprimir Extrato", icone_nome="printer")
        self.bt_extrato.setAutoDefault(False)
        self.bt_extrato.clicked.connect(self.imprimir_extrato)

        self.bt_csv = BotaoSecundario("Exportar CSV", icone_nome="download")
        self.bt_csv.setAutoDefault(False)
        self.bt_csv.clicked.connect(self.exportar_csv)

        layout.addWidget(self.bt_lancar_fiado)
        layout.addWidget(self.bt_pagar)
        layout.addStretch()
        layout.addWidget(self.bt_extrato)
        layout.addWidget(self.bt_csv)

        return layout

    _ICONES_FILTRO_TIMELINE = {
        "TODOS": "filter", "COMPRA": "shopping-cart", "PAGAMENTO": "dollar-sign",
        "AJUSTES": "refresh-cw", "30DIAS": "calendar",
    }

    _MESES = (
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
        "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    )

    _LARGURA_PAINEL_LATERAL = 290

    def _construir_painel_lateral(self):
        """Painel lateral recolhível: Detalhes (o que não está nos
        números grandes -- cadastro e estatísticas de perfil, em pares
        rótulo/valor como no painel de Clientes), Observações e, no fim,
        as ações raras e perigosas (excluir, LGPD) em tamanho discreto."""

        self.painel_lateral_expandido = True

        wrapper = QFrame()
        wrapper.setStyleSheet("background:transparent;")
        wrapper.setFixedWidth(self._LARGURA_PAINEL_LATERAL)

        layout_wrapper = QVBoxLayout(wrapper)
        layout_wrapper.setContentsMargins(0, 0, 0, 0)
        layout_wrapper.setSpacing(6)

        self.painel_lateral = SecaoCard("Detalhes", "user")

        self.bt_recolher_painel = QPushButton()
        self.bt_recolher_painel.setFixedSize(28, 28)
        self.bt_recolher_painel.setCursor(Qt.PointingHandCursor)
        self.bt_recolher_painel.setIcon(icone("chevron-right", cor=tokens.TEXTO_SECUNDARIO, tamanho=16))
        self.bt_recolher_painel.setToolTip("Recolher o painel de detalhes")
        self.bt_recolher_painel.setAccessibleName("Recolher o painel de detalhes")
        self.bt_recolher_painel.clicked.connect(self._alternar_painel_lateral)
        self.bt_recolher_painel.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)

        self.lbl_resumo_cpf = self._linha_resumo(self.painel_lateral, "CPF/CNPJ")
        self.lbl_resumo_email = self._linha_resumo(self.painel_lateral, "E-mail")
        self.lbl_resumo_endereco = self._linha_resumo(self.painel_lateral, "Endereço")
        self.lbl_resumo_cliente_desde = self._linha_resumo(self.painel_lateral, "Cliente desde")
        self.lbl_resumo_limite = self._linha_resumo(self.painel_lateral, "Limite de crédito")
        self.lbl_resumo_situacao = self._linha_resumo(self.painel_lateral, "Situação")
        self.lbl_resumo_maior_compra = self._linha_resumo(self.painel_lateral, "Maior compra")
        self.lbl_resumo_ticket_medio = self._linha_resumo(self.painel_lateral, "Ticket médio")
        self.lbl_resumo_ultimo_pagamento = self._linha_resumo(self.painel_lateral, "Último pagamento")

        separador = QFrame()
        separador.setFixedHeight(1)
        separador.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        self.painel_lateral.corpo.addSpacing(4)
        self.painel_lateral.corpo.addWidget(separador)

        lbl_obs_titulo = QLabel("OBSERVAÇÕES")
        lbl_obs_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800;
        """)
        self.painel_lateral.corpo.addWidget(lbl_obs_titulo)
        self.painel_lateral.corpo.addWidget(self._construir_pagina_observacoes())

        separador_2 = QFrame()
        separador_2.setFixedHeight(1)
        separador_2.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        self.painel_lateral.corpo.addSpacing(4)
        self.painel_lateral.corpo.addWidget(separador_2)

        self.painel_lateral.corpo.addWidget(
            self._botao_discreto("Excluir cliente", "trash-2", tokens.ERRO, self.excluir_cliente_atual)
        )

        if api.usuario_tem_permissao("clientes.lgpd"):
            self.painel_lateral.corpo.addWidget(self._botao_discreto(
                "Exportar dados (LGPD)", "download", tokens.TEXTO_SECUNDARIO,
                self.exportar_dados_lgpd_atual,
            ))
            self.painel_lateral.corpo.addWidget(self._botao_discreto(
                "Remover dados (LGPD)", "lock", tokens.ERRO, self.remover_dados_lgpd_atual,
            ))

        # o painel inteiro fica dentro da sua própria rolagem vertical --
        # em telas mais baixas (ex.: 1366x768) o conteúdo dele sozinho já
        # passaria da altura do diálogo. Só vertical: a largura é fixa.
        self.scroll_painel_lateral = QScrollArea()
        self.scroll_painel_lateral.setWidgetResizable(True)
        self.scroll_painel_lateral.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_painel_lateral.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }"
        )
        self.scroll_painel_lateral.setWidget(self.painel_lateral)

        linha_toggle = QHBoxLayout()
        linha_toggle.addStretch()
        linha_toggle.addWidget(self.bt_recolher_painel)

        layout_wrapper.addLayout(linha_toggle)
        layout_wrapper.addWidget(self.scroll_painel_lateral, stretch=1)

        self._painel_lateral_wrapper = wrapper
        self._atualizar_detalhes_cadastro(self.cliente)

        return wrapper

    def _botao_discreto(self, texto, icone_nome, cor, callback):

        botao = QPushButton(texto)
        botao.setIcon(icone(icone_nome, cor=cor, tamanho=14))
        botao.setCursor(Qt.PointingHandCursor)
        botao.setAutoDefault(False)
        botao.setMinimumHeight(32)
        botao.clicked.connect(callback)
        botao.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; border-radius:6px;
                color:{cor}; font-size:{tokens.TAMANHO_SM}px; font-weight:600;
                text-align:left; padding:0 8px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        return botao

    def _alternar_painel_lateral(self):

        self.painel_lateral_expandido = not self.painel_lateral_expandido

        self.scroll_painel_lateral.setVisible(self.painel_lateral_expandido)

        if self.painel_lateral_expandido:
            self._painel_lateral_wrapper.setFixedWidth(self._LARGURA_PAINEL_LATERAL)
            self.bt_recolher_painel.setIcon(icone("chevron-right", cor=tokens.TEXTO_SECUNDARIO, tamanho=16))
            self.bt_recolher_painel.setToolTip("Recolher o painel de detalhes")
        else:
            self._painel_lateral_wrapper.setFixedWidth(32)
            self.bt_recolher_painel.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=16))
            self.bt_recolher_painel.setToolTip("Mostrar o painel de detalhes")

    def _linha_resumo(self, secao, titulo):
        """Par rótulo à esquerda / valor à direita, como no painel do
        cliente selecionado em Clientes."""

        linha = QHBoxLayout()
        linha.setSpacing(12)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        lbl_valor = QLabel("—")
        lbl_valor.setWordWrap(True)
        lbl_valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)

        linha.addWidget(lbl_titulo, 0, Qt.AlignTop)
        linha.addWidget(lbl_valor, 1)

        secao.corpo.addLayout(linha)

        return lbl_valor

    def _construir_rodape(self):
        """Editar Cliente subiu pro cabeçalho (junto do resto das ações
        de contato) e Excluir/LGPD desceram pro painel lateral (embaixo
        de Observações) -- esse rodapé agora só segura o "Fechar",
        sempre no mesmo lugar previsível pra fechar a ficha."""

        rodape = QFrame()
        rodape.setStyleSheet(f"""
            background:{tokens.CARD}; border-top:1px solid {tokens.BORDA};
        """)

        layout = QHBoxLayout(rodape)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(10)

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.setMinimumHeight(42)
        bt_fechar.setAutoDefault(False)
        bt_fechar.clicked.connect(self.accept)

        layout.addStretch()
        layout.addWidget(bt_fechar)

        return rodape

    # ======================================
    # DADOS
    # ======================================

    def _atualizar_cabecalho(self, cliente):

        self.lbl_titulo.setText(cliente["nome"])

        ativo = cliente.get("ativo", True)
        self.badge_ativo.setText("Ativo" if ativo else "Inativo")
        variante = "sucesso" if ativo else "erro"
        fundo, cor_texto = Badge.variantes()[variante]
        self.badge_ativo.setStyleSheet(f"""
            background: {fundo}; color: {cor_texto};
            border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
            font-weight: 600; padding: 3px 10px;
        """)

        partes = [f"Cód. {cliente['id']}" if cliente.get("id") else ""]
        partes.append(cliente.get("telefone") or "Sem telefone")
        cidade = cliente.get("cidade")
        if cidade:
            partes.append(f"{cidade} – {cliente['estado']}" if cliente.get("estado") else cidade)
        self.lbl_subtitulo.setText("  ·  ".join(p for p in partes if p))

        self.bt_whatsapp.setEnabled(bool(cliente.get("telefone")))
        self.bt_ligar.setEnabled(bool(cliente.get("telefone")))
        self.bt_email.setEnabled(bool(cliente.get("email")))

        negativado = bool(cliente.get("negativado"))
        self.badge_negativado.setVisible(negativado)
        self.bt_negativar.setText("Desbloquear" if negativado else "Negativar")
        if negativado and cliente.get("negativado_motivo"):
            self.badge_negativado.setToolTip(f"Motivo: {cliente['negativado_motivo']}")

    def _alternar_negativado(self):
        nome = self.cliente["nome"]
        try:
            if self.cliente.get("negativado"):
                resposta = QMessageBox.question(
                    self, "Desbloquear cliente",
                    f"Desbloquear {nome}? Ele volta a poder comprar.\n\n"
                    "A dívida baixada continua como perda. Para cobrar de novo, "
                    "exclua o lançamento \"Perda\" no histórico.",
                )
                if resposta != QMessageBox.Yes:
                    return
                atualizado = desbloquear_cliente(self.cliente["id"])
            else:
                motivo, ok = pedir_texto(
                    self, "Negativar cliente", "Motivo (fica registrado)",
                    icone_nome="lock",
                    subtitulo=(
                        f"{nome} não poderá comprar nada e a dívida será "
                        "baixada como dinheiro perdido"
                    ),
                    texto_botao="Negativar",
                )
                if not ok or not motivo.strip():
                    return
                atualizado = negativar_cliente(self.cliente["id"], motivo.strip())
        except Exception as erro:
            QMessageBox.warning(self, "Não foi possível", str(erro))
            return
        self.cliente.update(atualizado)
        self._atualizar_cabecalho(self.cliente)
        self.carregar()

    def _atualizar_detalhes_cadastro(self, cliente):
        """Dados de cadastro no painel Detalhes -- separado de
        _atualizar_cabecalho porque o cabeçalho é montado antes do
        painel existir."""

        self.lbl_resumo_cpf.setText(cliente.get("cpf_cnpj") or "—")
        self.lbl_resumo_email.setText(cliente.get("email") or "—")
        self.lbl_resumo_endereco.setText(cliente.get("endereco") or "—")

        limite = cliente.get("limite_credito")
        self.lbl_resumo_limite.setText(formatar_moeda(limite) if limite else "Sem limite")

    def _atualizar_avatar(self, cliente):

        if not cliente.get("tem_foto"):
            return

        rodar_em_thread(
            self,
            obter_foto_cliente,
            cliente["id"],
            ao_sucesso=self._ao_atualizar_avatar_sucesso,
        )

    def _ao_atualizar_avatar_sucesso(self, foto_bytes):

        if not foto_bytes:
            return

        pixmap = QPixmap()
        pixmap.loadFromData(foto_bytes)

        self.avatar.setStyleSheet("background:transparent;")
        self.avatar.setPixmap(_pixmap_circular(pixmap, self.avatar.width()))

    def editar_cliente(self):

        from telas.cadastro_cliente import CadastroClienteDialog

        dialogo = CadastroClienteDialog(self.cliente, parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        if dialogo.cliente_salvo:
            self.cliente = dialogo.cliente_salvo
            self._atualizar_cabecalho(self.cliente)
            self._atualizar_detalhes_cadastro(self.cliente)
            self._atualizar_avatar(self.cliente)

    def excluir_cliente_atual(self):

        from services.cliente_service import excluir_cliente

        resposta = QMessageBox.question(
            self,
            "Excluir Cliente",
            f"Deseja desativar o cliente\n\n{self.cliente['nome']} ?"
        )

        if resposta != QMessageBox.Yes:
            return

        rodar_em_thread(
            self,
            excluir_cliente,
            self.cliente["id"],
            ao_sucesso=self._ao_excluir_cliente_sucesso,
            ao_erro=self._ao_movimento_mutacao_erro,
        )

    def _ao_excluir_cliente_sucesso(self, response):

        if response.status_code == 200:

            dados = response.json()

            if dados.get("aprovacao_pendente"):
                QMessageBox.information(
                    self,
                    "Aguardando aprovação",
                    dados.get("mensagem")
                    or "Pedido enviado — aguardando aprovação de um "
                    "administrador.",
                )
                # nao fecha a ficha: o cliente continua existindo ate
                # alguem aprovar
                return

            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def exportar_dados_lgpd_atual(self):

        from services.cliente_service import exportar_dados_lgpd

        response = exportar_dados_lgpd(self.cliente["id"])

        if response.status_code != 200:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        nome_arquivo = f"dados_lgpd_{self.cliente['nome'].replace(' ', '_')}.json"

        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Dados do Cliente (LGPD)",
            nome_arquivo,
            "Arquivo JSON (*.json)",
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".json"):
            caminho += ".json"

        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(response.json(), arquivo, ensure_ascii=False, indent=2)

        QMessageBox.information(
            self,
            "Sucesso",
            "Dados do cliente exportados com sucesso.",
        )

    def remover_dados_lgpd_atual(self):

        from services.cliente_service import remover_dados_lgpd

        resposta = QMessageBox.question(
            self,
            "Remover dados pessoais (LGPD)",
            "Isso vai apagar PERMANENTEMENTE os dados pessoais de "
            f"{self.cliente['nome']} (nome, CPF/CNPJ, telefone, "
            "e-mail, endereço, foto e observações) -- essa ação não "
            "pode ser desfeita.\n\n"
            "O histórico de vendas e fiado continua guardado (sem "
            "identificar mais a pessoa), pra manter os registros "
            "contábeis da loja.\n\n"
            "Tem certeza que quer continuar?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = remover_dados_lgpd(self.cliente["id"])

        if response.status_code == 200:
            QMessageBox.information(
                self,
                "Sucesso",
                response.json().get("mensagem") or "Dados removidos com sucesso.",
            )
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            _buscar_dados_ficha_cliente,
            self.cliente["id"],
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_lancar_fiado.setEnabled(not carregando)
        # bt_pagar fica de fora -- carregar() decide se ele deveria
        # estar habilitado (saldo > 0) assim que o saldo chegar

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar a ficha do cliente.\n{erro}"
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self.bt_lancar_fiado.setEnabled(not self.cliente.get("negativado"))

    def _ao_carregar_sucesso(self, resultado):

        saldo, self._vendas_por_id, self._nomes_produto, movimentos = resultado

        self.kpi_saldo.definir_valor(formatar_moeda(saldo))

        limite = float(self.cliente.get("limite_credito") or 0)
        if saldo <= 0:
            legenda_saldo = "Nada em aberto"
        elif limite > 0:
            legenda_saldo = f"{saldo / limite:.0%} do limite de {formatar_moeda(limite)}"
        else:
            legenda_saldo = "Sem limite de crédito definido"
        self.kpi_saldo.definir_legenda(legenda_saldo)

        self.bt_pagar.setEnabled(saldo > 0)

        # ordem cronologica (mais antigo primeiro) pra calcular o saldo
        # corrido — depois inverte só na hora de exibir
        movimentos_cron = sorted(
            movimentos, key=lambda m: m.get("data", "")
        )

        saldo_corrido = 0.0
        historico_calculado = []

        for mov in movimentos_cron:

            valor = float(mov.get("valor", 0) or 0)

            if mov.get("tipo") == "COMPRA":
                saldo_corrido += valor
            else:
                saldo_corrido -= valor

            historico_calculado.append((mov, saldo_corrido))

        historico_calculado.reverse()

        self._movimentos = historico_calculado
        self._timeline_qtd_exibida = self._TIMELINE_PAGINA

        self._preencher_timeline()

        self._atualizar_stats(movimentos_cron, saldo)
        self._carregar_observacoes()

    def _atualizar_stats(self, movimentos_cron, saldo_atual):

        agr = cliente_analise.calcular_agregados(self.cliente, movimentos_cron)

        total_comprado = agr["total_comprado"]
        total_pago = sum(
            float(m.get("valor", 0) or 0)
            for m in movimentos_cron
            if m.get("tipo") == "PAGAMENTO"
        )
        qtd_compras = agr["qtd_compras"]
        maior_compra = agr["maior_compra"]
        ticket_medio = total_comprado / qtd_compras if qtd_compras else 0

        def _data_curta(data):
            return data.strftime("%d/%m/%Y") if data else "—"

        def _ha_dias(dias):
            if dias is None:
                return "—"
            if dias == 0:
                return "Hoje"
            if dias == 1:
                return "Ontem"
            return f"Há {dias} dias"

        # números grandes
        self.kpi_comprado.definir_valor(formatar_moeda(total_comprado))
        self.kpi_comprado.definir_legenda(
            f"{qtd_compras} compra{'s' if qtd_compras != 1 else ''}"
            + (f" · média {formatar_moeda(ticket_medio)}" if qtd_compras else "")
        )

        self.kpi_pago.definir_valor(formatar_moeda(total_pago))
        self.kpi_pago.definir_legenda(
            f"último em {_data_curta(agr['ultimo_pagamento'])}"
            if agr["ultimo_pagamento"] else "nenhum pagamento ainda"
        )

        self.kpi_ultima_compra.definir_valor(_ha_dias(agr["dias_desde_ultima_compra"]))
        self.kpi_ultima_compra.definir_legenda(
            _data_curta(agr["ultima_compra"]) if agr["ultima_compra"] else "nenhuma compra ainda"
        )

        pontuacao = cliente_analise.calcular_pontuacao(agr)
        emoji_pont, _, texto_pontuacao = pontuacao.partition(" ")

        variante_pontuacao = {
            "🔴": "erro", "🟠": "alerta", "🟡": "alerta",
            "🔵": "info", "🟢": "sucesso",
        }.get(emoji_pont, "neutro")
        fundo_pont, cor_texto_pont = Badge.variantes()[variante_pontuacao]
        self.badge_pontuacao.setText(texto_pontuacao or pontuacao)
        self.badge_pontuacao.setStyleSheet(f"""
            background: {fundo_pont}; color: {cor_texto_pont};
            border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
            font-weight: 600; padding: 3px 10px;
        """)
        self.badge_pontuacao.setVisible(True)

        # aviso só quando há algo a avisar (vermelho/amarelo) -- o verde
        # ("Cliente Ativo") só repetia o selo do cabeçalho
        aviso = cliente_analise.calcular_aviso(agr)
        emoji_aviso, _, texto_aviso = aviso.partition(" ")
        cores_aviso = {
            "🔴": (tokens.ERRO_CLARO, tokens.ERRO),
            "🟡": (tokens.ALERTA_CLARO, tokens.ALERTA),
        }.get(emoji_aviso)

        if cores_aviso:
            cor_fundo, cor_texto = cores_aviso
            self.lbl_aviso_status.setText(texto_aviso or aviso)
            self.lbl_aviso_status.setStyleSheet(f"""
                background:{cor_fundo}; color:{cor_texto}; border:none;
                font-size:{tokens.TAMANHO_SM}px; font-weight:700;
                border-radius:{tokens.RADIUS_SM}px; padding:8px 14px;
            """)
            self.lbl_aviso_status.show()
        else:
            self.lbl_aviso_status.hide()

        # painel Detalhes
        self.lbl_resumo_cliente_desde.setText(_data_curta(agr["criado_em"]))
        self.lbl_resumo_situacao.setText(cliente_analise.status_financeiro(agr))
        self.lbl_resumo_maior_compra.setText(formatar_moeda(maior_compra))
        self.lbl_resumo_ticket_medio.setText(formatar_moeda(ticket_medio))
        self.lbl_resumo_ultimo_pagamento.setText(_data_curta(agr["ultimo_pagamento"]))

    def registrar_pagamento(self):

        self.bt_pagar.setEnabled(False)
        rodar_em_thread(
            self,
            saldo_cliente,
            self.cliente["id"],
            ao_sucesso=self._ao_saldo_para_pagamento_sucesso,
            ao_erro=self._ao_movimento_mutacao_erro,
            ao_finalizar=self._ao_saldo_pre_check_finalizado,
        )

    def _ao_saldo_pre_check_finalizado(self):
        self.bt_pagar.setEnabled(True)

    def _ao_saldo_para_pagamento_sucesso(self, saldo):

        if saldo <= 0:
            QMessageBox.information(
                self,
                "Fiado",
                "Este cliente não tem saldo devedor.",
            )
            return

        dialogo = RegistrarPagamentoDialog(
            self.cliente,
            saldo,
            parent=self,
        )

        if dialogo.exec() != QDialog.Accepted:
            return

        self.carregar()

    def lancar_fiado(self):

        self.bt_lancar_fiado.setEnabled(False)
        rodar_em_thread(
            self,
            saldo_cliente,
            self.cliente["id"],
            ao_sucesso=self._ao_saldo_para_fiado_sucesso,
            ao_erro=self._ao_movimento_mutacao_erro,
            ao_finalizar=self._ao_saldo_fiado_finalizado,
        )

    def _ao_saldo_fiado_finalizado(self):
        self.bt_lancar_fiado.setEnabled(True)

    def _ao_saldo_para_fiado_sucesso(self, saldo_atual):

        dialogo = LancarFiadoDialog(self.cliente, saldo_atual, parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        self.carregar()
