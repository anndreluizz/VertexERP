from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
)

from services.relatorio_service import (
    margem_categoria,
    estoque_categoria,
    vendas_dia_semana,
    vendas_dia_semana_hora,
    gasto_compras_mensal,
    ranking_fornecedores,
    prazo_fornecedores,
    categorias_sem_venda,
)
from services.loja_service import listar_lojas
from services.cliente_service import listar_clientes
from services.movimento_fiado_service import listar_movimentos
from services.user_service import listar_usuarios
from services import cliente_analise
from services.worker import rodar_em_thread, em_paralelo
from design import tokens
from design.charts import GraficoHeatmap
from utils.formatacao import formatar_moeda
from widgets.dialogs.message_dialog import Mensagem
from telas.relatorios.widgets import LinhaBarra, PainelSecao


_LIMIAR_INADIMPLENTE_ALTO = 500  # ver pergunta original do usuario


def _buscar_dados_indicadores(data_inicio, data_fim, loja_id):
    """Roda na worker thread -- chamadas independentes em paralelo,
    mais a agregacao de aging/limite de credito/funcionarios por loja
    (aging/limite reaproveitam cliente_analise, a mesma logica ja
    usada em telas/clientes.py, pra "inadimplente" nunca divergir
    entre as duas telas)."""

    (
        margens, estoques, dias_semana, heatmap_dia_hora, gasto_compras,
        fornecedores, prazos, categorias_paradas, clientes, movimentos,
        usuarios, lojas,
    ) = em_paralelo(
        (margem_categoria, data_inicio, data_fim, loja_id),
        (estoque_categoria, loja_id),
        (vendas_dia_semana, data_inicio, data_fim, loja_id),
        (vendas_dia_semana_hora, data_inicio, data_fim, loja_id),
        (gasto_compras_mensal, data_inicio, data_fim),
        (ranking_fornecedores, data_inicio, data_fim),
        (prazo_fornecedores,),
        (categorias_sem_venda,),
        (listar_clientes, loja_id),
        (listar_movimentos,),
        (listar_usuarios,),
        (listar_lojas,),
    )

    movimentos_por_cliente = {}
    for mov in movimentos:
        cid = mov.get("cliente_id")
        if cid is not None:
            movimentos_por_cliente.setdefault(cid, []).append(mov)

    agregados = [
        cliente_analise.calcular_agregados(
            cliente, movimentos_por_cliente.get(cliente["id"], [])
        )
        for cliente in clientes
    ]

    inadimplentes = [
        agr for agr in agregados if cliente_analise.eh_inadimplente(agr)
    ]

    aging = {"91-120": 0, "121-180": 0, "180+": 0}
    for agr in inadimplentes:
        dias = agr["dias_em_atraso"]
        if dias <= 120:
            aging["91-120"] += 1
        elif dias <= 180:
            aging["121-180"] += 1
        else:
            aging["180+"] += 1

    inadimplentes_valor_alto = sum(
        1 for agr in inadimplentes
        if agr["saldo_devedor"] >= _LIMIAR_INADIMPLENTE_ALTO
    )

    clientes_com_limite = sum(
        1 for c in clientes if float(c.get("limite_credito") or 0) > 0
    )

    nome_loja_por_id = {loja["id"]: loja["nome"] for loja in lojas}
    usuarios_por_loja: dict[str, int] = {}
    for usuario in usuarios:
        nome = nome_loja_por_id.get(usuario.get("loja_id"), "Sem loja definida")
        usuarios_por_loja[nome] = usuarios_por_loja.get(nome, 0) + 1

    return {
        "margem_categoria": margens,
        "estoque_categoria": estoques,
        "vendas_dia_semana": dias_semana,
        "heatmap_dia_hora": heatmap_dia_hora,
        "gasto_compras_mensal": gasto_compras,
        "ranking_fornecedores": fornecedores,
        "prazo_fornecedores": prazos,
        "categorias_sem_venda": categorias_paradas,
        "aging_inadimplencia": aging,
        "total_inadimplentes": len(inadimplentes),
        "inadimplentes_valor_alto": inadimplentes_valor_alto,
        "inadimplentes_valor_baixo": len(inadimplentes) - inadimplentes_valor_alto,
        "clientes_com_limite": clientes_com_limite,
        "clientes_sem_limite": len(clientes) - clientes_com_limite,
        "usuarios_por_loja": usuarios_por_loja,
    }


class IndicadoresMixin:
    """Aba Indicadores."""

    # ==========================================
    # PÁGINA: INDICADORES
    # ==========================================

    def _criar_pagina_indicadores(self):

        pagina, layout = self._pagina_rolavel(espacamento=12)

        filtro_layout = QHBoxLayout()
        filtro_layout.setSpacing(8)

        self.combo_periodo_indicadores = QComboBox()
        self.combo_periodo_indicadores.addItems(self.PERIODOS)
        self.combo_periodo_indicadores.setCurrentText("Este mês")
        self.combo_periodo_indicadores.setMinimumHeight(36)
        self.combo_periodo_indicadores.setCursor(Qt.PointingHandCursor)
        self.combo_periodo_indicadores.setStyleSheet(f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:4px 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """)

        self.combo_loja_indicadores = QComboBox()
        self.combo_loja_indicadores.setMinimumHeight(36)
        self.combo_loja_indicadores.setCursor(Qt.PointingHandCursor)
        self.combo_loja_indicadores.setStyleSheet(
            self.combo_periodo_indicadores.styleSheet()
        )
        self._carregar_combo_lojas(self.combo_loja_indicadores)

        self._timer_atualizar_indicadores = QTimer(self)
        self._timer_atualizar_indicadores.setSingleShot(True)
        self._timer_atualizar_indicadores.timeout.connect(
            self._atualizar_indicadores
        )
        self.combo_periodo_indicadores.currentTextChanged.connect(
            lambda: self._timer_atualizar_indicadores.start(300)
        )
        self.combo_loja_indicadores.currentIndexChanged.connect(
            lambda: self._timer_atualizar_indicadores.start(300)
        )

        filtro_layout.addWidget(self.combo_periodo_indicadores)
        filtro_layout.addWidget(self.combo_loja_indicadores)
        filtro_layout.addStretch()

        layout.addLayout(filtro_layout)

        # margem por categoria
        painel_margem = PainelSecao("💰", "Margem por Categoria")
        self.tabela_margem_categoria = QTableWidget()
        self.tabela_margem_categoria.setColumnCount(4)
        self.tabela_margem_categoria.setHorizontalHeaderLabels(
            ["Categoria", "Receita", "Lucro", "Margem %"]
        )
        self._estilizar_tabela(self.tabela_margem_categoria)
        self.tabela_margem_categoria.setMinimumHeight(160)
        painel_margem.corpo.addWidget(self.tabela_margem_categoria)
        layout.addWidget(painel_margem)

        # estoque por categoria (nao depende de periodo, so' de loja)
        painel_estoque_cat = PainelSecao("📦", "Estoque por Categoria")
        self.tabela_estoque_categoria = QTableWidget()
        self.tabela_estoque_categoria.setColumnCount(3)
        self.tabela_estoque_categoria.setHorizontalHeaderLabels(
            ["Categoria", "Quantidade", "Valor em Estoque"]
        )
        self._estilizar_tabela(self.tabela_estoque_categoria)
        self.tabela_estoque_categoria.setMinimumHeight(150)
        painel_estoque_cat.corpo.addWidget(self.tabela_estoque_categoria)
        layout.addWidget(painel_estoque_cat)

        # vendas por dia da semana
        self.painel_dia_semana = PainelSecao("📅", "Vendas por Dia da Semana")
        layout.addWidget(self.painel_dia_semana)

        # mapa de calor dia da semana x hora
        painel_heatmap = PainelSecao("🔥", "Quando a Loja Mais Vende")
        self.grafico_heatmap = GraficoHeatmap()
        painel_heatmap.corpo.addWidget(self.grafico_heatmap)
        layout.addWidget(painel_heatmap)

        # gasto mensal com compras
        self.painel_gasto_compras = PainelSecao("🛒", "Gasto Mensal com Compras")
        layout.addWidget(self.painel_gasto_compras)

        # ranking de fornecedores
        painel_fornecedores = PainelSecao("🏭", "Ranking de Fornecedores")
        self.tabela_fornecedores = QTableWidget()
        self.tabela_fornecedores.setColumnCount(3)
        self.tabela_fornecedores.setHorizontalHeaderLabels(
            ["Fornecedor", "Qtd. Compras", "Total"]
        )
        self._estilizar_tabela(self.tabela_fornecedores)
        self.tabela_fornecedores.setMinimumHeight(150)
        painel_fornecedores.corpo.addWidget(self.tabela_fornecedores)
        layout.addWidget(painel_fornecedores)

        # prazo medio de pagamento por fornecedor
        painel_prazo = PainelSecao("⏱️", "Prazo Médio de Pagamento por Fornecedor")
        subtitulo_prazo = QLabel(
            "Só considera compras a prazo (com parcelas geradas em "
            "Contas a Pagar)."
        )
        subtitulo_prazo.setWordWrap(True)
        subtitulo_prazo.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; border:none;"
        )
        painel_prazo.corpo.addWidget(subtitulo_prazo)
        self.tabela_prazo_fornecedores = QTableWidget()
        self.tabela_prazo_fornecedores.setColumnCount(3)
        self.tabela_prazo_fornecedores.setHorizontalHeaderLabels(
            ["Fornecedor", "Prazo Médio", "Qtd. Parcelas"]
        )
        self._estilizar_tabela(self.tabela_prazo_fornecedores)
        self.tabela_prazo_fornecedores.setMinimumHeight(150)
        painel_prazo.corpo.addWidget(self.tabela_prazo_fornecedores)
        layout.addWidget(painel_prazo)

        # categorias sem venda ha muito tempo
        painel_paradas = PainelSecao("🐌", "Categorias Sem Venda Há Mais de 90 Dias")
        self.tabela_categorias_paradas = QTableWidget()
        self.tabela_categorias_paradas.setColumnCount(2)
        self.tabela_categorias_paradas.setHorizontalHeaderLabels(
            ["Categoria", "Última Venda"]
        )
        self._estilizar_tabela(self.tabela_categorias_paradas)
        self.tabela_categorias_paradas.setMinimumHeight(120)
        painel_paradas.corpo.addWidget(self.tabela_categorias_paradas)
        layout.addWidget(painel_paradas)

        # aging de inadimplencia
        self.painel_aging = PainelSecao(
            "🔴", "Inadimplência por Tempo de Atraso e Valor"
        )
        subtitulo_aging = QLabel(
            "Mesmo critério da tela de Clientes: saldo devedor e mais "
            "de 90 dias sem nenhuma movimentação (compra ou pagamento)."
        )
        subtitulo_aging.setWordWrap(True)
        subtitulo_aging.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; border:none;"
        )
        self.painel_aging.layout_externo.insertWidget(1, subtitulo_aging)
        layout.addWidget(self.painel_aging)

        # limite de credito definido
        self.painel_limite_credito = PainelSecao(
            "🎯", "Limite de Crédito Definido"
        )
        layout.addWidget(self.painel_limite_credito)

        # funcionarios (usuarios do sistema) por loja
        self.painel_usuarios_loja = PainelSecao(
            "👥", "Usuários do Sistema por Loja"
        )
        subtitulo_usuarios = QLabel(
            "Contagem de logins, não necessariamente igual ao número "
            "real de funcionários (nem todo funcionário tem login, e "
            "o Vertex não tem módulo de RH/folha)."
        )
        subtitulo_usuarios.setWordWrap(True)
        subtitulo_usuarios.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; border:none;"
        )
        self.painel_usuarios_loja.layout_externo.insertWidget(1, subtitulo_usuarios)
        layout.addWidget(self.painel_usuarios_loja)

        layout.addStretch()

        return pagina

    def _atualizar_indicadores(self):

        if self._carregando_indicadores:
            return
        self._carregando_indicadores = True

        data_inicio, data_fim = self._calcular_periodo(
            self.combo_periodo_indicadores
        )
        loja_id = self.combo_loja_indicadores.currentData()

        rodar_em_thread(
            self,
            _buscar_dados_indicadores,
            data_inicio.isoformat() if data_inicio else None,
            data_fim.isoformat(),
            loja_id,
            ao_sucesso=self._ao_atualizar_indicadores_sucesso,
            ao_erro=self._ao_atualizar_indicadores_erro,
            ao_finalizar=self._ao_atualizar_indicadores_finalizado,
        )

    def _ao_atualizar_indicadores_erro(self, erro):
        Mensagem.erro(
            self, f"Não foi possível carregar os indicadores.\n{erro}"
        )

    def _ao_atualizar_indicadores_finalizado(self):
        self._carregando_indicadores = False

    def _ao_atualizar_indicadores_sucesso(self, dados):

        self._indicadores_carregados = True

        # margem por categoria
        margens = dados["margem_categoria"]
        self.tabela_margem_categoria.setRowCount(len(margens))
        for linha, item in enumerate(margens):
            self.tabela_margem_categoria.setItem(
                linha, 0, QTableWidgetItem(item["categoria"])
            )
            self.tabela_margem_categoria.setItem(
                linha, 1, QTableWidgetItem(formatar_moeda(item["receita"]))
            )
            self.tabela_margem_categoria.setItem(
                linha, 2, QTableWidgetItem(
                    "—" if item.get("custo_incompleto") else formatar_moeda(item["lucro"])
                )
            )
            self.tabela_margem_categoria.setItem(
                linha, 3, QTableWidgetItem(
                    "—" if item.get("custo_incompleto")
                    else f"{float(item['margem_pct']):.1f}%".replace(".", ",")
                )
            )

        # estoque por categoria
        estoques = dados["estoque_categoria"]
        self.tabela_estoque_categoria.setRowCount(len(estoques))
        for linha, item in enumerate(estoques):
            self.tabela_estoque_categoria.setItem(
                linha, 0, QTableWidgetItem(item["categoria"])
            )
            self.tabela_estoque_categoria.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade"]))
            )
            self.tabela_estoque_categoria.setItem(
                linha, 2, QTableWidgetItem(formatar_moeda(item["valor"]))
            )

        # vendas por dia da semana
        self.painel_dia_semana.limpar_corpo()
        dias_semana = dados["vendas_dia_semana"]
        maior_dia = max(
            (float(item["total"]) for item in dias_semana), default=0
        ) or 1

        for item in dias_semana:
            total = float(item["total"])
            self.painel_dia_semana.corpo.addWidget(LinhaBarra(
                item["dia_semana"],
                f"{item['quantidade']} venda(s)",
                formatar_moeda(total),
                total / maior_dia * 100,
                tokens.PRIMARIA,
            ))

        # mapa de calor dia da semana x hora
        self.grafico_heatmap.definir_dados(dados["heatmap_dia_hora"])

        # gasto mensal com compras
        self.painel_gasto_compras.limpar_corpo()
        gasto_compras = dados["gasto_compras_mensal"]

        if not gasto_compras:
            self.painel_gasto_compras.adicionar_vazio(
                "Nenhuma compra registrada no período."
            )
        else:
            maior_mes = max(
                (float(item["total"]) for item in gasto_compras), default=0
            ) or 1
            for item in gasto_compras:
                total = float(item["total"])
                self.painel_gasto_compras.corpo.addWidget(LinhaBarra(
                    item["mes"],
                    None,
                    formatar_moeda(total),
                    total / maior_mes * 100,
                    tokens.SECUNDARIA,
                ))

        # ranking de fornecedores
        fornecedores = dados["ranking_fornecedores"]
        self.tabela_fornecedores.setRowCount(len(fornecedores))
        for linha, item in enumerate(fornecedores):
            self.tabela_fornecedores.setItem(
                linha, 0, QTableWidgetItem(item["nome"])
            )
            self.tabela_fornecedores.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade_compras"]))
            )
            self.tabela_fornecedores.setItem(
                linha, 2, QTableWidgetItem(formatar_moeda(item["total"]))
            )

        # prazo medio de pagamento por fornecedor
        prazos = dados["prazo_fornecedores"]
        self.tabela_prazo_fornecedores.setRowCount(len(prazos))
        for linha, item in enumerate(prazos):
            self.tabela_prazo_fornecedores.setItem(
                linha, 0, QTableWidgetItem(item["nome"])
            )
            self.tabela_prazo_fornecedores.setItem(
                linha, 1,
                QTableWidgetItem(f"{item['prazo_medio_dias']:.0f} dias"),
            )
            self.tabela_prazo_fornecedores.setItem(
                linha, 2, QTableWidgetItem(str(item["quantidade_parcelas"]))
            )

        # categorias sem venda ha muito tempo
        categorias_paradas = dados["categorias_sem_venda"]
        self.tabela_categorias_paradas.setRowCount(len(categorias_paradas))
        for linha, item in enumerate(categorias_paradas):
            self.tabela_categorias_paradas.setItem(
                linha, 0, QTableWidgetItem(item["categoria"])
            )
            dias_sem_venda = item["dias_sem_venda"]
            texto_ultima = (
                "Nunca vendida" if dias_sem_venda is None
                else f"Há {dias_sem_venda} dias"
            )
            self.tabela_categorias_paradas.setItem(
                linha, 1, QTableWidgetItem(texto_ultima)
            )

        # aging de inadimplencia (tempo de atraso + faixa de valor)
        self.painel_aging.limpar_corpo()
        aging = dados["aging_inadimplencia"]
        total_inadimplentes = dados["total_inadimplentes"]

        if not total_inadimplentes:
            self.painel_aging.adicionar_vazio(
                "Nenhum cliente inadimplente no momento."
            )
        else:
            rotulos_aging = {
                "91-120": "91 a 120 dias",
                "121-180": "121 a 180 dias",
                "180+": "Mais de 180 dias",
            }
            for chave, rotulo in rotulos_aging.items():
                quantidade = aging[chave]
                self.painel_aging.corpo.addWidget(LinhaBarra(
                    rotulo,
                    None,
                    f"{quantidade} cliente(s)",
                    quantidade / total_inadimplentes * 100,
                    tokens.ERRO,
                ))

            limiar_texto = formatar_moeda(_LIMIAR_INADIMPLENTE_ALTO)
            valor_alto = dados["inadimplentes_valor_alto"]
            valor_baixo = dados["inadimplentes_valor_baixo"]

            self.painel_aging.corpo.addWidget(LinhaBarra(
                f"Saldo devedor ≥ {limiar_texto}",
                None,
                f"{valor_alto} cliente(s)",
                valor_alto / total_inadimplentes * 100,
                tokens.ERRO,
            ))
            self.painel_aging.corpo.addWidget(LinhaBarra(
                f"Saldo devedor < {limiar_texto}",
                None,
                f"{valor_baixo} cliente(s)",
                valor_baixo / total_inadimplentes * 100,
                tokens.ALERTA_TEXTO,
            ))

        # limite de credito
        self.painel_limite_credito.limpar_corpo()
        com_limite = dados["clientes_com_limite"]
        sem_limite = dados["clientes_sem_limite"]
        total_clientes = com_limite + sem_limite

        if not total_clientes:
            self.painel_limite_credito.adicionar_vazio(
                "Nenhum cliente cadastrado."
            )
        else:
            self.painel_limite_credito.corpo.addWidget(LinhaBarra(
                "Com limite definido",
                None,
                str(com_limite),
                com_limite / total_clientes * 100,
                tokens.SECUNDARIA_HOVER,
            ))
            self.painel_limite_credito.corpo.addWidget(LinhaBarra(
                "Sem limite definido (\"no olho\")",
                None,
                str(sem_limite),
                sem_limite / total_clientes * 100,
                tokens.ALERTA_TEXTO,
            ))

        # usuarios do sistema por loja
        self.painel_usuarios_loja.limpar_corpo()
        usuarios_por_loja = dados["usuarios_por_loja"]

        if not usuarios_por_loja:
            self.painel_usuarios_loja.adicionar_vazio(
                "Nenhum usuário cadastrado."
            )
        else:
            maior_qtd = max(usuarios_por_loja.values())
            for nome_loja, quantidade in sorted(
                usuarios_por_loja.items(), key=lambda i: i[1], reverse=True
            ):
                self.painel_usuarios_loja.corpo.addWidget(LinhaBarra(
                    nome_loja,
                    None,
                    str(quantidade),
                    quantidade / maior_qtd * 100,
                    tokens.PRIMARIA,
                ))
