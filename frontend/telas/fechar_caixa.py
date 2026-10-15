from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QFrame,
    QStackedWidget,
    QMessageBox,
    QWidget,
)

from services.caixa_service import caixa_aberto, resumo_caixa, fechar_caixa, listar_movimentos_caixa
from services import api, comprovante_service, impressora_termica_service, preferencias_service
from services.worker import rodar_em_thread, em_paralelo

from design import tokens
from design.widgets import (
    BotaoPerigo, BotaoSecundario, BotaoSucesso, CampoTexto, DialogoPadrao,
    campo_rotulado, cor_forma_pagamento, titulo_secao,
)
from utils.formatacao import formatar_moeda, linhas_resumo_caixa


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
    "PAGAMENTO": "Conta paga",
}


def _mostrar_linha(linha, visivel):
    """Mostra/esconde os rótulos de uma linha de _linha_valor (ela é
    um layout, que não tem setVisible)."""
    for i in range(linha.count()):
        widget = linha.itemAt(i).widget()
        if widget is not None:
            widget.setVisible(visivel)


def _formatar_data_curta(texto):
    texto = str(texto or "").replace("T", " ")[:16]
    try:
        return datetime.strptime(texto, "%Y-%m-%d %H:%M").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return texto


def _buscar_dados_fechamento():
    """Roda na worker thread -- caixa_aberto() + resumo_caixa(), os
    valores esperados que a pagina 2 (conferencia) vai comparar contra
    o que a pessoa contou na pagina 1. As 2 sao independentes, entao
    disparam em paralelo."""
    caixa, resumo = em_paralelo((caixa_aberto,), (resumo_caixa,))
    return caixa or {}, resumo or {}


def _confirmar_e_preparar_impressao(valor_contado, observacoes, caixa_id,
                                    valor_guardado=None, valor_retirado=None):
    """Roda na worker thread -- fecha o caixa e, se deu certo, ja'
    busca tudo que imprimir_extrato_dia() vai precisar (movimentos do
    dia, nome do responsavel, configuracoes da loja) numa tacada so',
    pra nao ficar re-buscando (e re-bloqueando a GUI thread) depois."""

    response = fechar_caixa(
        valor_contado=valor_contado,
        observacoes=observacoes,
        valor_guardado=valor_guardado,
        valor_retirado=valor_retirado,
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


def _texto_para_valor(texto):
    """Aceita '780', '780,5', '1.234,56' e '1234.56'; None se não for número."""
    texto = (texto or "").replace("R$", "").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return round(float(texto), 2)
    except ValueError:
        return None


class FecharCaixaWindow(DialogoPadrao):

    def __init__(self):

        super().__init__(
            "Fechar Caixa", "Etapa 1 de 2 · conte o dinheiro em espécie na gaveta",
            "lock", tokens.ALERTA, tokens.ALERTA_CLARO,
            largura=DialogoPadrao.MEDIO,
        )

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

        # ---- indicador de etapa (1. Contagem / 2. Conferência) ----

        linha_passos = QHBoxLayout()
        linha_passos.setSpacing(10)

        self.lbl_passo_1 = QLabel("1   Contagem")
        self.lbl_passo_2 = QLabel("2   Conferência")
        for lbl in (self.lbl_passo_1, self.lbl_passo_2):
            lbl.setAlignment(Qt.AlignCenter)
            linha_passos.addWidget(lbl, 1)

        self.corpo.addLayout(linha_passos)

        self.paginas = QStackedWidget()
        self.paginas.setStyleSheet("background:transparent;")

        self.pagina_contagem = self._criar_pagina_contagem()
        self.pagina_conferencia = self._criar_pagina_conferencia()

        self.paginas.addWidget(self.pagina_contagem)
        self.paginas.addWidget(self.pagina_conferencia)

        self.corpo.addWidget(self.paginas, stretch=1)

        # ---- rodapé: Cancelar + Continuar (etapa 1) / Voltar + Confirmar (etapa 2) ----

        self.bt_continuar = BotaoSucesso("Continuar", icone_nome="chevron-right")
        self.bt_continuar.setAutoDefault(False)
        self.bt_continuar.clicked.connect(self.avancar_para_conferencia)
        self.definir_botoes(self.bt_continuar)

        self.bt_voltar = BotaoSecundario("Voltar")
        self.bt_voltar.setAutoDefault(False)
        self.bt_voltar.setMinimumWidth(140)
        self.bt_voltar.clicked.connect(self.voltar_para_contagem)

        self.bt_confirmar = BotaoPerigo("Confirmar Fechamento", icone_nome="lock")
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.setMinimumWidth(200)
        self.bt_confirmar.clicked.connect(self.confirmar_fechamento)

        self.rodape.addWidget(self.bt_voltar)
        self.rodape.addWidget(self.bt_confirmar)

        self._marcar_passo_ativo(1)

        rodar_em_thread(
            self,
            _buscar_dados_fechamento,
            ao_sucesso=self._ao_dados_sucesso,
            ao_erro=self._ao_dados_erro,
        )

        self.ajustar_altura()
        self.valor_input.setFocus()

    def _ao_dados_sucesso(self, resultado):
        self.caixa, self.resumo = resultado
        self._dados_prontos = True

    def _ao_dados_erro(self, erro):
        self._erro_dados = erro

    def _marcar_passo_ativo(self, numero):
        """Realça o passo atual (1 ou 2) no indicador de etapa e troca os
        botões do rodapé -- deixa claro em que ponto do fluxo (contagem
        cega vs. conferência final) a pessoa está."""

        for n, lbl in ((1, self.lbl_passo_1), (2, self.lbl_passo_2)):
            if n == numero:
                lbl.setStyleSheet(f"""
                    background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA};
                    border:1.5px solid {tokens.PRIMARIA};
                    border-radius:{tokens.RADIUS_SM}px; font-weight:800;
                    font-size:{tokens.TAMANHO_MD}px; padding:9px 0;
                """)
            else:
                lbl.setStyleSheet(f"""
                    background:{tokens.FUNDO}; color:{tokens.TEXTO_TERCIARIO};
                    border:1.5px solid {tokens.BORDA};
                    border-radius:{tokens.RADIUS_SM}px; font-weight:600;
                    font-size:{tokens.TAMANHO_MD}px; padding:9px 0;
                """)

        etapa_1 = numero == 1
        self.bt_cancelar.setVisible(etapa_1)
        self.bt_continuar.setVisible(etapa_1)
        self.bt_voltar.setVisible(not etapa_1)
        self.bt_confirmar.setVisible(not etapa_1)

    # ======================================
    # PÁGINA 1 · CONTAGEM CEGA
    # ======================================

    def _criar_pagina_contagem(self):

        pagina = QWidget()

        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        aviso = QLabel(
            "Some todo o dinheiro físico presente na gaveta e informe o "
            "valor total contado. O sistema só mostra o valor esperado "
            "depois da contagem, pra não influenciar quem está contando."
        )
        aviso.setWordWrap(True)
        aviso.setStyleSheet(f"""
            background:{tokens.ALERTA_CLARO}; color:{tokens.ALERTA_TEXTO};
            font-size:{tokens.TAMANHO_BASE}px; border-radius:{tokens.RADIUS_SM}px;
            border-left:4px solid {tokens.ALERTA}; padding:12px 14px;
        """)
        layout.addWidget(aviso)

        # campo grande no mesmo formato do valor da tela de pagamento
        caixa_valor = QFrame()
        caixa_valor.setObjectName("caixaValor")
        caixa_valor.setStyleSheet(f"""
            QFrame#caixaValor {{
                background:{tokens.FUNDO}; border:1.5px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_MD}px;
            }}
        """)
        linha_valor = QHBoxLayout(caixa_valor)
        linha_valor.setContentsMargins(20, 6, 20, 6)

        lbl_rs = QLabel("R$")
        lbl_rs.setStyleSheet(f"""
            background:transparent; border:none; font-size:24px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.valor_input = QLineEdit()
        self.valor_input.setPlaceholderText("0,00")
        self.valor_input.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.valor_input.setMinimumHeight(70)
        self.valor_input.setStyleSheet(f"""
            QLineEdit {{
                font-size:40px; font-weight:800; color:{tokens.TEXTO};
                border:none; background:transparent;
            }}
        """)
        self.valor_input.returnPressed.connect(self.avancar_para_conferencia)

        linha_valor.addWidget(lbl_rs)
        linha_valor.addWidget(self.valor_input, 1)

        layout.addWidget(campo_rotulado(
            "Valor contado em espécie", caixa_valor,
            "Só o dinheiro (cédulas e moedas). PIX e cartão são conferidos "
            "na próxima etapa.  ·  Enter continua",
        ))

        layout.addStretch()

        return pagina

    def avancar_para_conferencia(self):

        valor = _texto_para_valor(self.valor_input.text())

        if valor is None:
            QMessageBox.warning(
                self,
                "Atenção",
                "Informe o valor contado na gaveta.",
            )
            return

        if valor < 0:
            QMessageBox.warning(
                self,
                "Atenção",
                "Informe um valor válido.",
            )
            return

        self.valor_contado = valor

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

        self.cabecalho.definir_texto(
            "Fechar Caixa", "Etapa 2 de 2 · confira os valores antes de encerrar"
        )
        self._marcar_passo_ativo(2)

        self.paginas.setCurrentWidget(self.pagina_conferencia)
        self.observacoes_input.setFocus()

    # ======================================
    # PÁGINA 2 · CONFERÊNCIA
    # ======================================

    def _linha_valor(self, rotulo, cor=None, destaque=False):

        cor = cor or tokens.TEXTO
        tamanho = tokens.TAMANHO_MD if destaque else tokens.TAMANHO_BASE
        peso_rotulo = 700 if destaque else 400

        linha = QHBoxLayout()

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tamanho}px;
            font-weight:{peso_rotulo}; color:{tokens.TEXTO_SECUNDARIO};
        """)

        lbl_valor = QLabel("R$ 0,00")
        lbl_valor.setAlignment(Qt.AlignRight)
        lbl_valor.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tamanho}px; font-weight:700; color:{cor};
        """)

        linha.addWidget(lbl_rotulo)
        linha.addWidget(lbl_valor)

        return linha, lbl_valor

    def _separador(self):

        linha = QFrame()
        linha.setFixedHeight(1)
        linha.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        return linha

    def _bloco(self):

        bloco = QFrame()
        bloco.setObjectName("blocoResumo")
        bloco.setStyleSheet(f"""
            QFrame#blocoResumo {{
                background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_MD}px;
            }}
        """)
        layout = QVBoxLayout(bloco)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)
        return bloco, layout

    def _cartao_numero(self, titulo):
        """Cartão do topo da conferência: rótulo pequeno + valor grande."""

        cartao = QFrame()
        cartao.setObjectName("cartaoNumero")
        layout = QVBoxLayout(cartao)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        lbl_titulo = QLabel(titulo.upper())
        lbl_valor = QLabel("R$ 0,00")
        lbl_extra = QLabel("")

        layout.addWidget(lbl_titulo)
        layout.addWidget(lbl_valor)
        layout.addWidget(lbl_extra)

        cartao.lbl_titulo, cartao.lbl_valor, cartao.lbl_extra = lbl_titulo, lbl_valor, lbl_extra
        self._pintar_cartao(cartao, tokens.TEXTO, tokens.FUNDO, tokens.BORDA)
        return cartao

    def _pintar_cartao(self, cartao, cor, fundo, borda):

        cartao.setStyleSheet(f"""
            QFrame#cartaoNumero {{
                background:{fundo}; border:1.5px solid {borda};
                border-radius:{tokens.RADIUS_MD}px;
            }}
        """)
        cartao.lbl_titulo.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
            font-weight:800; color:{tokens.TEXTO_SECUNDARIO}; letter-spacing:0.5px;
        """)
        cartao.lbl_valor.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XXL}px;
            font-weight:800; color:{cor};
        """)
        cartao.lbl_extra.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_SM}px;
            font-weight:700; color:{cor};
        """)

    def _criar_pagina_conferencia(self):

        pagina = QWidget()

        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # ---- os 3 números que importam: previsto x contado = diferença ----

        linha_cartoes = QHBoxLayout()
        linha_cartoes.setSpacing(12)

        self.cartao_previsto = self._cartao_numero("Previsto em espécie")
        self.cartao_contado = self._cartao_numero("Contado na gaveta")
        self.cartao_diferenca = self._cartao_numero("Diferença")

        # mesma largura nos 3 (o stretch sozinho cede pro texto maior)
        largura_cartao = (DialogoPadrao.MEDIO - 2 * 28 - 2 * 12) // 3
        for cartao in (self.cartao_previsto, self.cartao_contado, self.cartao_diferenca):
            cartao.setFixedWidth(largura_cartao)
            linha_cartoes.addWidget(cartao, 1)

        layout.addLayout(linha_cartoes)

        # nomes antigos -- o resto do arquivo (e o extrato) lê daqui
        self.lbl_total_previsto = self.cartao_previsto.lbl_valor
        self.lbl_valor_contado = self.cartao_contado.lbl_valor
        self.lbl_diferenca = self.cartao_diferenca.lbl_valor

        # ---- detalhamento em 2 colunas ----

        bloco_previsto, bloco_layout = self._bloco()

        linha, self.lbl_troco_inicial = self._linha_valor("Troco inicial")
        bloco_layout.addLayout(linha)

        linha, self.lbl_vendas_dinheiro = self._linha_valor("Vendas em dinheiro")
        bloco_layout.addLayout(linha)

        linha, self.lbl_fiado_dinheiro = self._linha_valor("Fiado recebido em dinheiro")
        bloco_layout.addLayout(linha)

        linha, self.lbl_suprimentos = self._linha_valor(
            "Suprimentos", cor=tokens.SECUNDARIA_HOVER
        )
        bloco_layout.addLayout(linha)

        linha, self.lbl_sangrias = self._linha_valor("Sangrias", cor=tokens.ERRO)
        bloco_layout.addLayout(linha)

        # so caixa antigo: boleto pago em dinheiro saia da gaveta
        self.linha_contas, self.lbl_contas = self._linha_valor(
            "Contas pagas (boleto)", cor=tokens.ERRO
        )
        bloco_layout.addLayout(self.linha_contas)

        bloco_layout.addWidget(self._separador())

        linha, self.lbl_previsto_bloco = self._linha_valor(
            "Total previsto", cor=tokens.PRIMARIA, destaque=True
        )
        bloco_layout.addLayout(linha)
        bloco_layout.addStretch()

        bloco_outros, outros_layout = self._bloco()

        linha, self.lbl_vendas_pix = self._linha_valor(
            "Vendas PIX", cor=cor_forma_pagamento("PIX")
        )
        outros_layout.addLayout(linha)

        linha, self.lbl_fiado_pix = self._linha_valor(
            "Fiado recebido no PIX", cor=cor_forma_pagamento("PIX")
        )
        outros_layout.addLayout(linha)

        linha, self.lbl_vendas_cartao = self._linha_valor(
            "Vendas cartão", cor=cor_forma_pagamento("CARTAO")
        )
        outros_layout.addLayout(linha)

        linha, self.lbl_fiado_cartao = self._linha_valor(
            "Fiado recebido no cartão", cor=cor_forma_pagamento("CARTAO")
        )
        outros_layout.addLayout(linha)

        self.linha_fiado_outros, self.lbl_fiado_outros = self._linha_valor(
            "Fiado recebido (outras formas)"
        )
        outros_layout.addLayout(self.linha_fiado_outros)

        outros_layout.addStretch()
        outros_layout.addWidget(self._separador())

        linha, self.lbl_total_geral = self._linha_valor(
            "Total geral do turno", cor=tokens.PRIMARIA, destaque=True
        )
        outros_layout.addLayout(linha)

        # crediario nao entrou dinheiro: fica fora do total, como nota
        linha, self.lbl_vendas_prazo = self._linha_valor(
            "Vendas no crediário (não soma)", cor=cor_forma_pagamento("PRAZO")
        )
        outros_layout.addLayout(linha)

        col_dinheiro = QVBoxLayout()
        col_dinheiro.setSpacing(8)
        col_dinheiro.addWidget(titulo_secao("Dinheiro na gaveta"))
        col_dinheiro.addWidget(bloco_previsto, 1)

        col_outros = QVBoxLayout()
        col_outros.setSpacing(8)
        col_outros.addWidget(titulo_secao("Outras formas do turno"))
        col_outros.addWidget(bloco_outros, 1)

        colunas = QHBoxLayout()
        colunas.setSpacing(16)
        colunas.addLayout(col_dinheiro, 1)
        colunas.addLayout(col_outros, 1)
        layout.addLayout(colunas)

        # pra onde vai o dinheiro da gaveta: alimenta o "dinheiro guardado"
        # da Inteligencia de Negocios (o resto fica de troco pro proximo dia)
        layout.addWidget(titulo_secao("Para onde vai o dinheiro da gaveta"))
        self.guardado_input = CampoTexto("0,00")
        self.retirado_input = CampoTexto("0,00")
        self.guardado_input.textChanged.connect(self._atualizar_troco)
        self.retirado_input.textChanged.connect(self._atualizar_troco)
        self.lbl_fica_troco = QLabel()
        self.lbl_fica_troco.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SECUNDARIO}; "
            f"font-size:{tokens.TAMANHO_SM}px;"
        )
        destino = QHBoxLayout()
        destino.setSpacing(16)
        destino.addWidget(campo_rotulado("Vai para o cofre/banco (R$)", self.guardado_input), 1)
        destino.addWidget(campo_rotulado("Retirada dos sócios (R$)", self.retirado_input), 1)
        layout.addLayout(destino)
        layout.addWidget(self.lbl_fica_troco)

        self.observacoes_input = CampoTexto(
            "Ex.: diferença por troco errado, sangria não registrada..."
        )
        layout.addWidget(campo_rotulado("Observações (opcional)", self.observacoes_input))

        layout.addStretch()

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
        vendas_prazo = float(r.get("vendas_prazo", 0) or 0)
        total_geral = float(r.get("total_geral", 0) or 0)

        self.lbl_troco_inicial.setText(formatar_moeda(saldo_inicial))
        self.lbl_vendas_dinheiro.setText(formatar_moeda(vendas_dinheiro))
        self.lbl_fiado_dinheiro.setText(formatar_moeda(float(r.get("recebimentos_fiado_dinheiro", 0) or 0)))
        contas = float(r.get("contas_pagas_caixa", 0) or 0)
        self.lbl_contas.setText(f"- {formatar_moeda(contas)}")
        _mostrar_linha(self.linha_contas, abs(contas) >= 0.01)
        self.lbl_suprimentos.setText(f"+ {formatar_moeda(suprimentos)}")
        self.lbl_sangrias.setText(f"- {formatar_moeda(sangrias)}")
        self.lbl_previsto_bloco.setText(formatar_moeda(total_previsto))

        self.lbl_total_previsto.setText(formatar_moeda(total_previsto))
        self.cartao_previsto.lbl_extra.setText("troco + entradas − sangrias")
        self.cartao_previsto.lbl_extra.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        self.lbl_valor_contado.setText(formatar_moeda(self.valor_contado))
        # padrao: tudo que foi contado vai pro cofre/banco
        self.guardado_input.setText(formatar_moeda(self.valor_contado, com_simbolo=False))
        self.retirado_input.setText("0,00")
        self._atualizar_troco()
        self.cartao_contado.lbl_extra.setText("o que você informou na etapa 1")
        self.cartao_contado.lbl_extra.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        diferenca = self.valor_contado - total_previsto

        if abs(diferenca) < 0.01:
            cor, fundo = tokens.SECUNDARIA_HOVER, tokens.SUCESSO_CLARO
            texto, extra = "R$ 0,00", "Confere ✓"
        elif diferenca > 0:
            cor, fundo = tokens.PRIMARIA, tokens.PRIMARIA_CLARA
            texto, extra = f"+ {formatar_moeda(diferenca)}", "Sobrando na gaveta"
        else:
            cor, fundo = tokens.ERRO, tokens.ERRO_CLARO
            texto, extra = f"- {formatar_moeda(abs(diferenca))}", "Faltando na gaveta"

        self._pintar_cartao(self.cartao_diferenca, cor, fundo, cor)
        self.lbl_diferenca.setText(texto)
        self.cartao_diferenca.lbl_extra.setText(extra)

        self.lbl_vendas_pix.setText(formatar_moeda(vendas_pix))
        self.lbl_vendas_cartao.setText(formatar_moeda(vendas_cartao))
        self.lbl_fiado_pix.setText(formatar_moeda(float(r.get("recebimentos_fiado_pix", 0) or 0)))
        self.lbl_fiado_cartao.setText(formatar_moeda(float(r.get("recebimentos_fiado_cartao", 0) or 0)))
        fiado_outros = float(r.get("recebimentos_fiado_outros", 0) or 0)
        self.lbl_fiado_outros.setText(formatar_moeda(fiado_outros))
        _mostrar_linha(self.linha_fiado_outros, abs(fiado_outros) >= 0.01)
        self.lbl_vendas_prazo.setText(formatar_moeda(vendas_prazo))
        self.lbl_total_geral.setText(formatar_moeda(total_geral))

    def voltar_para_contagem(self):

        self.cabecalho.definir_texto(
            "Fechar Caixa", "Etapa 1 de 2 · conte o dinheiro em espécie na gaveta"
        )
        self._marcar_passo_ativo(1)

        self.paginas.setCurrentWidget(self.pagina_contagem)
        self.valor_input.setFocus()
        self.valor_input.selectAll()

    def _destino(self):
        """(guardado, retirado, troco) ou None se algum valor e' invalido
        ou se tira mais do que foi contado."""
        guardado = _texto_para_valor(self.guardado_input.text() or "0")
        retirado = _texto_para_valor(self.retirado_input.text() or "0")
        if guardado is None or retirado is None or guardado < 0 or retirado < 0:
            return None
        troco = round(self.valor_contado - guardado - retirado, 2)
        if troco < -0.009:
            return None
        return guardado, retirado, troco

    def _atualizar_troco(self, *_):
        destino = self._destino()
        if destino is None:
            self.lbl_fica_troco.setText(
                "Valores inválidos: cofre/banco + retirada não pode passar do contado."
            )
        else:
            self.lbl_fica_troco.setText(
                f"Fica na gaveta de troco: {formatar_moeda(destino[2])}"
            )

    def confirmar_fechamento(self):

        destino = self._destino()
        if destino is None:
            QMessageBox.warning(
                self, "Fechar Caixa",
                "Confira os valores de cofre/banco e retirada: a soma não pode "
                "passar do dinheiro contado na gaveta.",
            )
            return

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
            destino[0],
            destino[1],
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

    def imprimir_extrato_dia(self, movimentos, responsavel, config):
        imprimir_fechamento(
            self, self.caixa, self.resumo, movimentos, self.valor_contado,
            self.observacoes_input.text().strip(), responsavel,
            datetime.now().isoformat(), config,
        )


def montar_html_fechamento(caixa, resumo, movimentos, valor_contado, observacoes,
                           responsavel, fechado_em, config):
    """HTML do extrato de fechamento -- usado ao fechar o caixa e ao
    reimprimir um caixa antigo (telas/caixas_anteriores.py).
    valor_contado None = caixa fechado sem contagem."""

    nome_loja = config.get("nome_loja") or "Vertex ERP"
    telefone_loja = config.get("telefone") or ""

    agora = _formatar_data_curta(fechado_em)

    total_previsto = float(resumo.get("total_previsto", 0) or 0)
    diferenca = (valor_contado or 0) - total_previsto

    if valor_contado is None:
        cor_diferenca, texto_diferenca = "#666", "não contado"
    elif abs(diferenca) < 0.01:
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
        for rotulo, valor in linhas_resumo_caixa(resumo)
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

    texto_obs = (observacoes or "").strip()
    bloco_observacoes = (
        f"<h3>Observações</h3><p>{texto_obs}</p>" if texto_obs else ""
    )

    return f"""
    <div style="text-align:center;">
        <h2 style="margin-bottom:0;">{nome_loja}</h2>
        <div style="color:#666;">{f"WhatsApp: {telefone_loja}" if telefone_loja else ""}</div>
    </div>
    <hr>
    <h3 style="text-align:center; margin-bottom:4px;">
        Extrato de Fechamento de Caixa
    </h3>
    <table width="100%" cellspacing="4">
        <tr><td><b>Aberto em:</b></td>
            <td>{_formatar_data_curta(caixa.get('data_abertura'))}</td></tr>
        <tr><td><b>Fechado em:</b></td><td>{agora}</td></tr>
        <tr><td><b>Responsável:</b></td><td>{responsavel}</td></tr>
    </table>
    <h3>Resumo do Turno</h3>
    <table width="100%" cellspacing="4">
        {linhas_resumo}
        <tr><td><b>Total previsto</b></td>
            <td align="right"><b>{formatar_moeda(total_previsto)}</b></td></tr>
        <tr><td>Valor contado</td>
            <td align="right">{formatar_moeda(valor_contado) if valor_contado is not None else '—'}</td></tr>
        <tr><td>Diferença</td>
            <td align="right" style="color:{cor_diferenca};">
                <b>{texto_diferenca}</b></td></tr>
    </table>
    <h3 style="text-align:right;">
        Total geral do turno: {formatar_moeda(resumo.get('total_geral', 0))}
    </h3>
    <p style="color:#666;">Vendas a prazo (fiado lançado, não entra nos totais):
        {formatar_moeda(resumo.get('vendas_prazo', 0))}</p>
    <h3>Movimentações do Dia</h3>
    <table width="100%" border="1" cellspacing="0" cellpadding="6">
        <tr style="background:#f0f0f0;">
            <th>Data</th><th>Tipo</th><th>Descrição</th><th>Valor</th>
        </tr>
        {linhas_movimentos}
    </table>
    {bloco_observacoes}
    """


def imprimir_fechamento(parent, caixa, resumo, movimentos, valor_contado, observacoes,
                        responsavel, fechado_em, config):
    """Termica de 80mm se estiver ativa; senao (ou se falhar e a pessoa
    quiser) a janela normal do Windows."""

    config_impressora = preferencias_service.carregar_impressora_termica()

    if config_impressora and config_impressora.get("ativa"):

        ok, erro = impressora_termica_service.imprimir_fechamento_caixa(
            caixa, resumo, movimentos, valor_contado, observacoes or "",
            responsavel, fechado_em, config, config_impressora,
        )

        if ok:
            return

        resposta = QMessageBox.question(
            parent,
            "Falha na impressora térmica",
            f"{erro}\n\nQuer tentar imprimir pela janela normal do Windows?",
        )

        if resposta != QMessageBox.Yes:
            return

    comprovante_service.imprimir(
        montar_html_fechamento(
            caixa, resumo, movimentos, valor_contado, observacoes,
            responsavel, fechado_em, config,
        ),
        parent,
    )
