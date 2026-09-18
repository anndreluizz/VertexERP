from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QFrame,
    QStackedWidget,
    QMessageBox,
    QPushButton,
)

from services.caixa_service import caixa_aberto, resumo_caixa, fechar_caixa, listar_movimentos_caixa
from services import api, comprovante_service, impressora_termica_service, preferencias_service
from services.worker import rodar_em_thread, em_paralelo

from design import tokens
from design.icons import icone, icone_pixmap
from design.responsive import tamanho_fixo_seguro
from design.widgets import BotaoPerigo, BotaoSecundario, BotaoSucesso
from utils.formatacao import formatar_moeda


# rotulos de tipo de movimento em texto puro pro extrato do dia --
# mesmos usados na tela de caixa (ver telas/caixa.py), so' que sem
# cor aqui (cupom termico e' texto puro, e o HTML do extrato usa uma
# tabela simples, sem as pills coloridas da tela)
_ROTULOS_TIPO_MOVIMENTO = {
    "VENDA": "Venda",
    "SUPRIMENTO": "Suprimento",
    "SANGRIA": "Sangria",
    "RECEBIMENTO_FIADO": "Recebimento fiado",
    "ESTORNO": "Estorno",
}


def _formatar_data_curta(texto):
    texto = str(texto or "")
    if "T" in texto:
        texto = texto.replace("T", " ")
    return texto[:16]


def _buscar_dados_fechamento():
    """Roda na worker thread -- caixa_aberto() + resumo_caixa(), os
    valores esperados que a pagina 2 (conferencia) vai comparar contra
    o que a pessoa contou na pagina 1. As 2 sao independentes, entao
    disparam em paralelo."""
    caixa, resumo = em_paralelo((caixa_aberto,), (resumo_caixa,))
    return caixa or {}, resumo or {}


def _confirmar_e_preparar_impressao(valor_contado, observacoes, caixa_id):
    """Roda na worker thread -- fecha o caixa e, se deu certo, ja'
    busca tudo que imprimir_extrato_dia() vai precisar (movimentos do
    dia, nome do responsavel, configuracoes da loja) numa tacada so',
    pra nao ficar re-buscando (e re-bloqueando a GUI thread) depois."""

    response = fechar_caixa(
        valor_contado=valor_contado,
        observacoes=observacoes,
    )

    if response.status_code != 200:
        return response, None, None, None

    # as 3 chamadas abaixo so' dependem do fechamento ja' ter dado
    # certo (acima), nao uma da outra -- disparam em paralelo
    movimentos_brutos, usuario, config = em_paralelo(
        (listar_movimentos_caixa, caixa_id) if caixa_id else (lambda: [],),
        (api.me,),
        (api.configuracoes,),
    )

    movimentos = sorted(movimentos_brutos, key=lambda m: m.get("data", ""))
    responsavel = (usuario or {}).get("nome") or "—"

    return response, movimentos, responsavel, config


class FecharCaixaWindow(QDialog):

    def __init__(self):
        super().__init__()

        # pagina 1 (contagem cega) nao depende desses dados -- de
        # proposito, pra nao enviesar quem esta contando o dinheiro
        # fisico mostrando o valor esperado antes da hora. Busca em
        # segundo plano enquanto a pessoa conta (o dialogo nao trava
        # esperando isso); avancar_para_conferencia() confere se ja
        # chegou antes de usar.
        self.caixa = {}
        self.resumo = {}
        self._dados_prontos = False
        self._erro_dados = None
        self.valor_contado = 0.0

        self.setWindowTitle("Fechar Caixa")
        tamanho_fixo_seguro(self, 460, 680)
        self.setStyleSheet(f"background:{tokens.CARD};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        cabecalho_linha = QHBoxLayout()
        cabecalho_linha.setContentsMargins(24, 20, 24, 0)
        cabecalho_linha.setSpacing(14)

        icone_circulo = QLabel()
        icone_circulo.setFixedSize(48, 48)
        icone_circulo.setAlignment(Qt.AlignCenter)
        icone_circulo.setStyleSheet(f"""
            background:{tokens.ALERTA_CLARO}; border-radius:24px;
        """)
        icone_circulo.setPixmap(icone_pixmap("lock", cor=tokens.ALERTA, tamanho=20))
        cabecalho_linha.addWidget(icone_circulo)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(2)

        self.lbl_titulo = QLabel("Conferência de Caixa")
        self.lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)

        self.lbl_subtitulo = QLabel(
            "Conte o dinheiro em espécie na gaveta"
        )
        self.lbl_subtitulo.setWordWrap(True)
        self.lbl_subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        col_titulo.addWidget(self.lbl_titulo)
        col_titulo.addWidget(self.lbl_subtitulo)

        cabecalho_linha.addLayout(col_titulo, 1)

        bt_fechar = QPushButton()
        bt_fechar.setFixedSize(30, 30)
        bt_fechar.setCursor(Qt.PointingHandCursor)
        bt_fechar.setAutoDefault(False)
        bt_fechar.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        bt_fechar.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        bt_fechar.clicked.connect(self.reject)
        cabecalho_linha.addWidget(bt_fechar, 0, Qt.AlignTop)

        raiz.addLayout(cabecalho_linha)

        # ---- indicador de etapa (1. Contagem / 2. Conferência) ----

        linha_passos = QHBoxLayout()
        linha_passos.setContentsMargins(24, 14, 24, 0)
        linha_passos.setSpacing(8)

        self.lbl_passo_1 = QLabel("1. Contagem")
        self.lbl_passo_2 = QLabel("2. Conferência")
        self.lbl_passo_1.setAlignment(Qt.AlignCenter)
        self.lbl_passo_2.setAlignment(Qt.AlignCenter)

        linha_passos.addWidget(self.lbl_passo_1, 1)
        linha_passos.addWidget(self.lbl_passo_2, 1)

        raiz.addLayout(linha_passos)

        self._marcar_passo_ativo(1)

        self.paginas = QStackedWidget()

        self.pagina_contagem = self._criar_pagina_contagem()
        self.pagina_conferencia = self._criar_pagina_conferencia()

        self.paginas.addWidget(self.pagina_contagem)
        self.paginas.addWidget(self.pagina_conferencia)

        raiz.addWidget(self.paginas, stretch=1)

        rodar_em_thread(
            self,
            _buscar_dados_fechamento,
            ao_sucesso=self._ao_dados_sucesso,
            ao_erro=self._ao_dados_erro,
        )

    def _ao_dados_sucesso(self, resultado):
        self.caixa, self.resumo = resultado
        self._dados_prontos = True

    def _ao_dados_erro(self, erro):
        self._erro_dados = erro

    def _marcar_passo_ativo(self, numero):
        """Realça o passo atual (1 ou 2) no indicador de etapa no topo
        do diálogo -- deixa claro em que ponto do fluxo (contagem cega
        vs. conferência final) a pessoa está."""

        for n, lbl in ((1, self.lbl_passo_1), (2, self.lbl_passo_2)):
            if n == numero:
                lbl.setStyleSheet(f"""
                    background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA};
                    border-radius:{tokens.RADIUS_PILL}px; font-weight:700;
                    font-size:{tokens.TAMANHO_XS}px; padding:6px 0;
                """)
            else:
                lbl.setStyleSheet(f"""
                    background:transparent; color:{tokens.TEXTO_TERCIARIO};
                    font-weight:600; font-size:{tokens.TAMANHO_XS}px; padding:6px 0;
                """)

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
        aviso.setStyleSheet(f"""
            background:{tokens.ALERTA_CLARO}; color:{tokens.ALERTA_TEXTO};
            font-size:{tokens.TAMANHO_SM}px; border-radius:{tokens.RADIUS_SM}px;
            padding:12px;
        """)

        layout.addWidget(aviso)

        lbl_valor_titulo = QLabel("VALOR CONTADO EM ESPÉCIE")
        lbl_valor_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.valor_input = QLineEdit()
        self.valor_input.setPlaceholderText("R$ 0,00")
        self.valor_input.setAlignment(Qt.AlignCenter)
        self.valor_input.setStyleSheet(f"""
            QLineEdit {{
                font-size:40px; font-weight:800; color:{tokens.TEXTO};
                border:none; border-bottom:2px solid {tokens.BORDA};
                padding:10px 0; background:transparent;
            }}
        """)

        layout.addWidget(lbl_valor_titulo)
        layout.addWidget(self.valor_input)

        layout.addStretch()

        rodape = QHBoxLayout()
        rodape.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.clicked.connect(self.reject)

        bt_continuar = BotaoSucesso("Continuar")
        bt_continuar.setMinimumHeight(46)
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

        if self._erro_dados is not None:
            QMessageBox.critical(
                self,
                "Erro",
                f"Não foi possível carregar os dados do caixa "
                f"pra comparar.\n{self._erro_dados}",
            )
            return

        if not self._dados_prontos:
            # bem raro na pratica (a busca roda desde que o dialogo
            # abriu, e contar dinheiro fisico leva mais tempo que
            # isso) -- mas se acontecer, e' melhor avisar do que
            # avancar com valor esperado zerado
            QMessageBox.information(
                self,
                "Aguarde",
                "Ainda carregando os dados do caixa. Tente de novo "
                "em um instante.",
            )
            return

        self.preencher_conferencia()

        self.lbl_titulo.setText("Resumo do Fechamento")
        self.lbl_subtitulo.setText(
            "Confira os valores antes de encerrar o caixa"
        )
        self._marcar_passo_ativo(2)

        self.paginas.setCurrentWidget(self.pagina_conferencia)

    # ======================================
    # PÁGINA 2 · CONFERÊNCIA
    # ======================================

    def _linha_valor(self, rotulo, cor=None):

        cor = cor or tokens.TEXTO

        linha = QHBoxLayout()

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tokens.TAMANHO_SM}px; color:{tokens.TEXTO_SECUNDARIO};
        """)

        lbl_valor = QLabel("R$ 0,00")
        lbl_valor.setAlignment(Qt.AlignRight)
        lbl_valor.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tokens.TAMANHO_SM}px; font-weight:700; color:{cor};
        """)

        linha.addWidget(lbl_rotulo)
        linha.addWidget(lbl_valor)

        return linha, lbl_valor

    def _separador(self):

        linha = QFrame()
        linha.setFixedHeight(1)
        linha.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        return linha

    def _criar_pagina_conferencia(self):

        pagina = QFrame()

        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        bloco_previsto = QFrame()
        bloco_previsto.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
        """)
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
            "Suprimentos", cor=tokens.SECUNDARIA_HOVER
        )
        bloco_layout.addLayout(linha)

        linha, self.lbl_sangrias = self._linha_valor(
            "Sangrias", cor=tokens.ERRO
        )
        bloco_layout.addLayout(linha)

        bloco_layout.addWidget(self._separador())

        linha, self.lbl_total_previsto = self._linha_valor(
            "Total previsto em espécie", cor=tokens.PRIMARIA
        )
        bloco_layout.addLayout(linha)

        layout.addWidget(bloco_previsto)

        bloco_contado = QFrame()
        bloco_contado.setStyleSheet(f"""
            background:{tokens.CARD}; border:1px solid {tokens.BORDA};
            border-radius:{tokens.RADIUS_SM}px;
        """)
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

        lbl_obs_titulo = QLabel("OBSERVAÇÕES (OPCIONAL)")
        lbl_obs_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)
        layout.addWidget(lbl_obs_titulo)

        self.observacoes_input = QLineEdit()
        self.observacoes_input.setPlaceholderText(
            "Ex.: diferença por troco errado, sangria não registrada..."
        )
        self.observacoes_input.setMinimumHeight(40)
        self.observacoes_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_SM}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QLineEdit:focus {{ border: 1.5px solid {tokens.PRIMARIA}; }}
        """)
        layout.addWidget(self.observacoes_input)

        bloco_outros = QFrame()
        bloco_outros.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
        """)
        outros_layout = QVBoxLayout(bloco_outros)
        outros_layout.setContentsMargins(16, 14, 16, 14)
        outros_layout.setSpacing(8)

        linha, self.lbl_vendas_pix = self._linha_valor("Vendas PIX")
        outros_layout.addLayout(linha)

        linha, self.lbl_vendas_cartao = self._linha_valor("Vendas cartão")
        outros_layout.addLayout(linha)

        outros_layout.addWidget(self._separador())

        linha, self.lbl_total_geral = self._linha_valor(
            "Total geral do turno", cor=tokens.PRIMARIA
        )
        outros_layout.addLayout(linha)

        layout.addWidget(bloco_outros)

        layout.addStretch()

        rodape = QHBoxLayout()
        rodape.setSpacing(10)

        bt_voltar = BotaoSecundario("Voltar")
        bt_voltar.setMinimumHeight(46)
        bt_voltar.clicked.connect(self.voltar_para_contagem)

        self.bt_confirmar = BotaoPerigo("Confirmar Fechamento")
        self.bt_confirmar.setMinimumHeight(46)
        self.bt_confirmar.clicked.connect(self.confirmar_fechamento)

        rodape.addWidget(bt_voltar)
        rodape.addWidget(self.bt_confirmar)

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

        self.lbl_troco_inicial.setText(formatar_moeda(saldo_inicial))
        self.lbl_vendas_dinheiro.setText(formatar_moeda(vendas_dinheiro))
        self.lbl_suprimentos.setText(f"+ {formatar_moeda(suprimentos)}")
        self.lbl_sangrias.setText(f"- {formatar_moeda(sangrias)}")
        self.lbl_total_previsto.setText(formatar_moeda(total_previsto))

        self.lbl_valor_contado.setText(formatar_moeda(self.valor_contado))

        diferenca = self.valor_contado - total_previsto

        if abs(diferenca) < 0.01:
            cor = tokens.SECUNDARIA_HOVER
            texto = "R$ 0,00 (confere)"
        elif diferenca > 0:
            cor = tokens.PRIMARIA
            texto = f"+ {formatar_moeda(diferenca)} (sobra)"
        else:
            cor = tokens.ERRO
            texto = f"- {formatar_moeda(abs(diferenca))} (falta)"

        self.lbl_diferenca.setText(texto)
        self.lbl_diferenca.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tokens.TAMANHO_SM}px; font-weight:700; color:{cor};
        """)

        self.lbl_vendas_pix.setText(formatar_moeda(vendas_pix))
        self.lbl_vendas_cartao.setText(formatar_moeda(vendas_cartao))
        self.lbl_total_geral.setText(formatar_moeda(total_geral))

    def voltar_para_contagem(self):

        self.lbl_titulo.setText("Conferência de Caixa")
        self.lbl_subtitulo.setText("Conte o dinheiro em espécie na gaveta")
        self._marcar_passo_ativo(1)

        self.paginas.setCurrentWidget(self.pagina_contagem)

    def confirmar_fechamento(self):

        resposta = QMessageBox.question(
            self,
            "Fechar Caixa",
            "Confirmar o fechamento do caixa? Esta ação não "
            "pode ser desfeita.",
        )

        if resposta != QMessageBox.Yes:
            return

        # sem UI otimista aqui de proposito: fechar caixa e' uma
        # mutacao financeira irreversivel (o proprio dialogo ja avisa
        # isso) -- so' fecha/mostra sucesso depois da resposta real.
        self.bt_confirmar.setEnabled(False)

        rodar_em_thread(
            self,
            _confirmar_e_preparar_impressao,
            self.valor_contado,
            self.observacoes_input.text().strip() or None,
            self.caixa.get("id"),
            ao_sucesso=self._ao_confirmar_sucesso,
            ao_erro=self._ao_confirmar_erro,
            ao_finalizar=self._ao_confirmar_finalizado,
        )

    def _ao_confirmar_sucesso(self, resultado):

        response, movimentos, responsavel, config = resultado

        if response.status_code != 200:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", erro)
            return

        self.imprimir_extrato_dia(movimentos, responsavel, config)

        self.accept()

    def _ao_confirmar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_confirmar_finalizado(self):
        self.bt_confirmar.setEnabled(True)

    # ======================================
    # EXTRATO COMPLETO DO DIA -- impresso automaticamente ao
    # confirmar o fechamento, pra conferência em papel do turno
    # inteiro (mesmo padrão de impressora térmica com fallback pro
    # diálogo normal do Windows usado no extrato do cliente, ver
    # ficha_cliente.py)
    # ======================================

    def _montar_html_extrato_dia(self, movimentos, config, responsavel):

        nome_loja = config.get("nome_loja") or "Vertex ERP"
        telefone_loja = config.get("telefone") or ""

        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        total_previsto = float(self.resumo.get("total_previsto", 0) or 0)
        diferenca = self.valor_contado - total_previsto

        if abs(diferenca) < 0.01:
            cor_diferenca, texto_diferenca = "#16A34A", "R$ 0,00 (confere)"
        elif diferenca > 0:
            cor_diferenca = "#2563EB"
            texto_diferenca = f"+ {formatar_moeda(diferenca)} (sobra)"
        else:
            cor_diferenca = "#DC2626"
            texto_diferenca = f"- {formatar_moeda(abs(diferenca))} (falta)"

        linhas_resumo = "".join(
            f"<tr><td>{rotulo}</td>"
            f"<td align='right'>{formatar_moeda(valor)}</td></tr>"
            for rotulo, valor in (
                ("Troco inicial", self.resumo.get("saldo_inicial", 0)),
                ("Vendas em dinheiro", self.resumo.get("vendas_dinheiro", 0)),
                ("Vendas PIX", self.resumo.get("vendas_pix", 0)),
                ("Vendas cartão", self.resumo.get("vendas_cartao", 0)),
                ("Vendas a prazo", self.resumo.get("vendas_prazo", 0)),
                ("Suprimentos", self.resumo.get("suprimentos", 0)),
                ("Sangrias", self.resumo.get("sangrias", 0)),
                ("Recebimentos fiado", self.resumo.get("recebimentos_fiado", 0)),
            )
        )

        linhas_movimentos = "".join(
            f"<tr>"
            f"<td>{_formatar_data_curta(mov.get('data'))}</td>"
            f"<td>{_ROTULOS_TIPO_MOVIMENTO.get(mov.get('tipo'), mov.get('tipo') or '—')}</td>"
            f"<td>{mov.get('descricao') or ''}</td>"
            f"<td align='right'>{formatar_moeda(mov.get('valor', 0))}</td>"
            f"</tr>"
            for mov in movimentos
        ) or (
            "<tr><td colspan='4' align='center'>"
            "Nenhuma movimentação registrada.</td></tr>"
        )

        texto_obs = self.observacoes_input.text().strip()
        bloco_observacoes = (
            f"<h3>Observações</h3><p>{texto_obs}</p>" if texto_obs else ""
        )

        return f"""
        <div style="text-align:center;">
            <h2 style="margin-bottom:0;">{nome_loja}</h2>
            <div style="color:#666;">{telefone_loja}</div>
        </div>
        <hr>
        <h3 style="text-align:center; margin-bottom:4px;">
            Extrato de Fechamento de Caixa
        </h3>
        <table width="100%" cellspacing="4">
            <tr><td><b>Aberto em:</b></td>
                <td>{_formatar_data_curta(self.caixa.get('data_abertura'))}</td></tr>
            <tr><td><b>Fechado em:</b></td><td>{agora}</td></tr>
            <tr><td><b>Responsável:</b></td><td>{responsavel}</td></tr>
        </table>
        <h3>Resumo do Turno</h3>
        <table width="100%" cellspacing="4">
            {linhas_resumo}
            <tr><td><b>Total previsto</b></td>
                <td align="right"><b>{formatar_moeda(total_previsto)}</b></td></tr>
            <tr><td>Valor contado</td>
                <td align="right">{formatar_moeda(self.valor_contado)}</td></tr>
            <tr><td>Diferença</td>
                <td align="right" style="color:{cor_diferenca};">
                    <b>{texto_diferenca}</b></td></tr>
        </table>
        <h3 style="text-align:right;">
            Total geral: {formatar_moeda(self.resumo.get('total_geral', 0))}
        </h3>
        <h3>Movimentações do Dia</h3>
        <table width="100%" border="1" cellspacing="0" cellpadding="6">
            <tr style="background:#f0f0f0;">
                <th>Data</th><th>Tipo</th><th>Descrição</th><th>Valor</th>
            </tr>
            {linhas_movimentos}
        </table>
        {bloco_observacoes}
        """

    def imprimir_extrato_dia(self, movimentos, responsavel, config):

        # impressao em si fica sincrona -- e' I/O de dispositivo local
        # (porta serial/USB da impressora termica, ou o dialogo de
        # impressao do Windows), nao rede; fora do escopo deste audit
        config_impressora = preferencias_service.carregar_impressora_termica()

        if config_impressora and config_impressora.get("ativa"):

            ok, erro = impressora_termica_service.imprimir_fechamento_caixa(
                self.caixa,
                self.resumo,
                movimentos,
                self.valor_contado,
                self.observacoes_input.text().strip(),
                responsavel,
                datetime.now().isoformat(),
                config,
                config_impressora,
            )

            if ok:
                return

            resposta = QMessageBox.question(
                self,
                "Falha na impressora térmica",
                f"{erro}\n\nQuer tentar imprimir pela janela normal do Windows?",
            )

            if resposta != QMessageBox.Yes:
                return

        comprovante_service.imprimir(
            self._montar_html_extrato_dia(movimentos, config, responsavel), self
        )
