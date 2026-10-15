"""Inteligencia de Negocios (/bi/resumo): numeros que o dono usa pra
decidir -- consolidado = soma das lojas, sem duplicar; fiado por idade
da compra mais antiga em aberto; contas por vencimento; permissao."""

from datetime import date, datetime, timedelta

from app.models.caixa import Caixa
from app.models.cliente import Cliente
from app.models.conta_pagar import ContaPagar
from app.models.item_venda import ItemVenda
from app.models.loja import Loja
from app.models.movimento_caixa import MovimentoCaixa
from app.models.movimento_fiado import MovimentoFiado
from app.models.venda import Venda

HOJE = date.today()


def _resumo(client, headers, loja_id=None, inicio=HOJE, fim=HOJE):
    params = {"data_inicio": inicio.isoformat(), "data_fim": fim.isoformat()}
    if loja_id is not None:
        params["loja_id"] = loja_id
    return client.get("/bi/resumo", params=params, headers=headers)


def _venda(db, produto, loja, valor, forma, status="FINALIZADA"):
    venda = Venda(
        valor_total=valor, desconto=0, forma_pagamento=forma,
        status=status, data=datetime.now(), loja_id=loja.id,
    )
    db.add(venda)
    db.flush()
    db.add(ItemVenda(
        venda_id=venda.id, produto_id=produto.id, quantidade=1,
        valor_unitario=valor, subtotal=valor,
    ))
    db.commit()


def _lojas(db):
    matriz, filial = Loja(nome="Matriz", ativa=True), Loja(nome="Filial", ativa=True)
    db.add_all([matriz, filial])
    db.commit()
    return matriz, filial


def test_consolidado_e_a_soma_das_lojas_sem_duplicar(client, auth_headers, db, produto):
    matriz, filial = _lojas(db)
    _venda(db, produto, matriz, 100, "DINHEIRO")
    _venda(db, produto, matriz, 50, "PRAZO")
    _venda(db, produto, filial, 30, "PIX")
    _venda(db, produto, filial, 999, "DINHEIRO", status="CANCELADA")

    todas = _resumo(client, auth_headers).json()
    so_filial = _resumo(client, auth_headers, loja_id=filial.id).json()

    vendas = todas["vendas"]
    assert float(vendas["faturamento_liquido"]) == 180
    assert vendas["quantidade"] == 3
    assert float(vendas["a_vista"]) == 130
    assert float(vendas["a_prazo"]) == 50
    assert float(vendas["ticket_medio"]) == 60

    por_loja = {l["loja_nome"]: l for l in todas["lojas"]}
    assert float(por_loja["Matriz"]["faturamento_liquido"]) == 150
    assert float(por_loja["Filial"]["faturamento_liquido"]) == 30
    assert sum(float(l["faturamento_liquido"]) for l in todas["lojas"]) == 180

    assert float(so_filial["vendas"]["faturamento_liquido"]) == 30
    assert so_filial["periodo"]["loja_nome"] == "Filial"
    assert so_filial["lojas"] == []


def test_periodo_sem_movimento_zera_sem_erro(client, auth_headers):
    resposta = _resumo(client, auth_headers, inicio=HOJE - timedelta(days=400),
                       fim=HOJE - timedelta(days=399))

    assert resposta.status_code == 200
    dados = resposta.json()
    assert float(dados["vendas"]["faturamento_liquido"]) == 0
    assert dados["vendas"]["quantidade"] == 0
    assert dados["vendas"]["mais_vendidos"] == []
    assert float(dados["fiado"]["saldo_em_aberto"]) == 0
    assert "Nenhuma venda registrada ainda." in dados["avisos"]


def test_lucro_desconhecido_sem_custo(client, auth_headers, db, produto):
    matriz, _ = _lojas(db)
    produto.preco_custo = 0
    db.commit()
    _venda(db, produto, matriz, 20, "DINHEIRO")

    dados = _resumo(client, auth_headers).json()

    assert dados["vendas"]["lucro_bruto"] is None
    assert dados["vendas"]["custo_incompleto"] is True
    assert any("sem custo cadastrado" in a for a in dados["avisos"])


def test_fiado_por_idade_da_compra_mais_antiga_em_aberto(client, auth_headers, db, usuario):
    def cliente(nome, telefone):
        c = Cliente(nome=nome, email=f"{nome}@x.com", telefone=telefone, ativo=True)
        db.add(c)
        db.commit()
        return c

    def mov(c, tipo, valor, dias_atras):
        db.add(MovimentoFiado(
            cliente_id=c.id, usuario_id=usuario.id, tipo=tipo, valor=valor,
            data=datetime.now() - timedelta(days=dias_atras),
        ))

    # 100 de 200 dias atras ja pago; resta a compra de 40 dias: faixa 31-60
    ana = cliente("Ana", "1199")
    mov(ana, "COMPRA", 100, 200)
    mov(ana, "COMPRA", 80, 40)
    mov(ana, "PAGAMENTO", 100, 10)
    # pagou so' uma parte da compra de 100 dias: continua na faixa 91-180
    bia = cliente("Bia", None)
    mov(bia, "COMPRA", 300, 100)
    mov(bia, "PAGAMENTO", 50, 5)
    # quitado: nao conta
    caio = cliente("Caio", None)
    mov(caio, "COMPRA", 20, 50)
    mov(caio, "HAVER", 20, 1)
    db.commit()

    fiado = _resumo(client, auth_headers).json()["fiado"]

    assert float(fiado["saldo_em_aberto"]) == 330
    assert fiado["clientes_devendo"] == 2
    assert fiado["devedores_sem_telefone"] == 1
    faixas = {f["de_dias"]: (f["clientes"], float(f["total"])) for f in fiado["faixas_atraso"]}
    assert faixas[31] == (1, 80)
    assert faixas[91] == (1, 250)
    assert [d["nome"] for d in fiado["maiores_devedores"]] == ["Bia", "Ana"]
    assert fiado["maiores_devedores"][1]["dias_em_atraso"] == 40


def test_contas_por_vencimento_e_previsao(client, auth_headers, db, produto, usuario):
    matriz, _ = _lojas(db)
    agora = datetime.now()

    def conta(valor, dias, status="PENDENTE"):
        db.add(ContaPagar(valor=valor, data_vencimento=agora + timedelta(days=dias),
                          status=status, loja_id=matriz.id,
                          data_pagamento=agora if status == "PAGO" else None))

    conta(10, -3)    # vencida
    conta(20, 2)     # 7 e 30 dias
    conta(40, 20)    # 30 dias
    conta(80, 60)    # depois
    conta(5, -1, status="PAGO")
    caixa = Caixa(saldo_inicial=0, saldo_final=70, status="ABERTO",
                  usuario_id=usuario.id, loja_id=matriz.id)
    db.add(caixa)
    db.commit()
    db.add(MovimentoCaixa(caixa_id=caixa.id, usuario_id=usuario.id,
                          tipo="RECEBIMENTO_FIADO", valor=60, forma_pagamento="PIX",
                          descricao="Pagamento fiado - X"))
    db.commit()
    _venda(db, produto, matriz, 30, "DINHEIRO")

    dados = _resumo(client, auth_headers).json()
    contas = dados["contas_pagar"]

    assert float(contas["vencidas"]["total"]) == 10
    assert float(contas["proximos_7_dias"]["total"]) == 20
    assert float(contas["proximos_30_dias"]["total"]) == 60
    assert float(contas["pendentes_total"]["total"]) == 150
    assert float(contas["pagas_no_periodo"]) == 5
    assert float(dados["recebimentos"]["fiado_recebido"]) == 60
    assert float(dados["caixa"]["dinheiro_nas_gavetas"]) == 70
    assert float(dados["caixa"]["entrou_no_periodo"]) == 30 + 60

    prev = dados["previsao_30_dias"]
    # 1 dia de historico: (30 a vista + 60 fiado) / 1 dia * 30
    assert prev["dias_de_base"] == 1
    assert float(prev["entradas_estimadas"]) == 2700
    assert float(prev["saidas_previstas"]) == 70
    assert float(prev["saldo_previsto"]) == 70 + 2700 - 70


def test_sem_permissao_nao_ve(client, auth_headers_comum):
    assert _resumo(client, auth_headers_comum).status_code == 403


def test_usuario_preso_a_loja_so_ve_a_dele(client, db, produto, usuario_comum):
    from app.models.perfil import Perfil

    matriz, filial = _lojas(db)
    _venda(db, produto, matriz, 100, "DINHEIRO")
    _venda(db, produto, filial, 30, "PIX")
    perfil = Perfil(nome="Gerente BI", permissoes=["bi.ver"])
    db.add(perfil)
    db.commit()
    usuario_comum.perfil_id = perfil.id
    usuario_comum.loja_id = filial.id
    db.commit()
    token = client.post(
        "/auth/login", json={"email": usuario_comum.email, "senha": "123456"}
    ).json()["access_token"]

    dados = _resumo(client, {"Authorization": f"Bearer {token}"}, loja_id=matriz.id).json()

    assert dados["periodo"]["loja_id"] == filial.id
    assert float(dados["vendas"]["faturamento_liquido"]) == 30


def test_data_final_antes_da_inicial(client, auth_headers):
    resposta = _resumo(client, auth_headers, inicio=HOJE, fim=HOJE - timedelta(days=1))
    assert resposta.status_code == 400


# ---------------- recomendacoes (regras puras, sem banco) ----------------

from copy import deepcopy
from decimal import Decimal

from app.services.bi_service import recomendacoes

SAUDAVEL = {
    "periodo": {"data_inicio": date(2026, 10, 1), "data_fim": date(2026, 10, 30),
                "dias": 30, "loja_nome": "Todas as lojas"},
    "vendas": {"a_prazo": Decimal("100"), "faturamento_liquido": Decimal("1000"),
               "quantidade": 50, "produtos_sem_venda": {"quantidade": 0, "exemplos": []}},
    "recebimentos": {"fiado_recebido": Decimal("150")},
    "fiado": {"faixas_atraso": [{"de_dias": 0, "clientes": 1, "total": Decimal("50")},
                                {"de_dias": 91, "clientes": 0, "total": Decimal("0")}],
              "maiores_devedores": [], "saldo_em_aberto": Decimal("50"),
              "clientes_devendo": 1, "devedores_sem_telefone": 0, "acima_do_limite": 0},
    "contas_pagar": {"vencidas": {"quantidade": 0, "total": Decimal("0")},
                     "proximos_7_dias": {"quantidade": 0, "total": Decimal("0")},
                     "proximas": []},
    "previsao_30_dias": {"dias_de_base": 30, "saldo_previsto": Decimal("500"),
                         "saidas_previstas": Decimal("100"), "entradas_estimadas": Decimal("600"),
                         "media_diaria_entradas": Decimal("20"), "dinheiro_nas_gavetas": Decimal("0")},
    "qualidade_dados": {"produtos_ativos": 10, "produtos_sem_custo": 0,
                        "produtos_sem_estoque_minimo": 0, "dias_de_historico": 90},
    "lojas": [],
}


def _com(**mudancas):
    r = deepcopy(SAUDAVEL)
    for caminho, valor in mudancas.items():
        alvo = r
        *pais, chave = caminho.split("__")
        for p in pais:
            alvo = alvo[p]
        alvo[chave] = valor
    return [(x["prioridade"], x["problema"]) for x in recomendacoes(r)]


def test_empresa_saudavel_nao_gera_alarme():
    assert recomendacoes(deepcopy(SAUDAVEL)) == []


def test_cada_regra_dispara_com_a_prioridade_certa():
    assert _com(contas_pagar__vencidas={"quantidade": 2, "total": Decimal("300")})[0][0] == "critica"
    # falta no mes, mas a semana cabe no caixa: alta
    assert _com(previsao_30_dias__saldo_previsto=Decimal("-10"))[0][0] == "alta"
    # e a semana nao cabe: critica
    r = deepcopy(SAUDAVEL)
    r["previsao_30_dias"]["saldo_previsto"] = Decimal("-10")
    r["contas_pagar"]["proximos_7_dias"]["total"] = Decimal("1000")
    assert recomendacoes(r)[0]["prioridade"] == "critica"

    antigo = [{"de_dias": 91, "clientes": 3, "total": Decimal("900")}]
    assert ("alta", "Fiado com mais de 90 dias em aberto.") in _com(fiado__faixas_atraso=antigo)
    assert _com(recebimentos__fiado_recebido=Decimal("10"))[0][1].startswith("O fiado está crescendo")
    assert _com(vendas__a_prazo=Decimal("600"),
                recebimentos__fiado_recebido=Decimal("600"))[0][1].endswith("a maior parte das vendas é a prazo.")
    assert _com(fiado__acima_do_limite=2)[0][0] == "media"
    assert _com(fiado__devedores_sem_telefone=1)[0][0] == "media"
    assert _com(qualidade_dados__produtos_sem_custo=3)[0][0] == "media"
    assert _com(qualidade_dados__produtos_sem_estoque_minimo=3)[0][0] == "baixa"


def test_nao_conclui_com_poucos_dados():
    # poucas vendas: nao julga a participacao a prazo
    assert _com(vendas__a_prazo=Decimal("600"), vendas__quantidade=5,
                recebimentos__fiado_recebido=Decimal("600")) == []
    # sem historico de entradas: nao faz previsao
    assert _com(previsao_30_dias__saldo_previsto=Decimal("-10"),
                previsao_30_dias__dias_de_base=0) == []
    # produto parado so' conta com 30+ dias de historico
    parado = {"quantidade": 1, "exemplos": [{"produto": "X", "estoque": 5}]}
    assert _com(vendas__produtos_sem_venda=parado, qualidade_dados__dias_de_historico=10) == []
    assert _com(vendas__produtos_sem_venda=parado)[0][0] == "baixa"


def test_resumo_traz_recomendacoes_ordenadas(client, auth_headers, db, produto):
    matriz, _ = _lojas(db)
    produto.preco_custo = 0
    db.add(ContaPagar(valor=50, data_vencimento=datetime.now() - timedelta(days=2),
                      loja_id=matriz.id))
    db.commit()

    recs = _resumo(client, auth_headers).json()["recomendacoes"]

    prioridades = [r["prioridade"] for r in recs]
    assert prioridades[0] == "critica"
    assert prioridades == sorted(prioridades, key=["critica", "alta", "media", "baixa"].index)
    assert all({"problema", "evidencias", "impacto", "acao", "prazo", "indicador"} <= r.keys()
               for r in recs)
