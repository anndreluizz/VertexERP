from urllib.parse import quote

from services.api import get, post, delete, endpoint_com_loja

# a API nunca devolve mais que isso por chamada (ver vendas.py no
# backend) -- listar_vendas() varre todas as paginas por baixo dos
# panos, entao quem usa isso pra somar/analisar (dashboard, fiado,
# "mais vendidos", relatorios) continua vendo o historico completo,
# sem truncar silenciosamente em 100 registros.
_TAMANHO_PAGINA = 500


def listar_vendas(loja_id=None, cliente_id=None, desde=None):
    """loja_id=None busca de TODAS as lojas de propósito -- usado pra
    montar o histórico de compras de um cliente (ficha_cliente.py,
    clientes.py), que não é restrito por loja (ver Cliente.loja_id).
    Quem precisa da visão de uma loja só (dashboard.py, visao_geral.py)
    passa o loja_id do terminal explicitamente. cliente_id/desde (date)
    filtram no backend -- sem eles a lista cresce com a loja toda."""

    vendas = []
    skip = 0

    while True:

        lote = listar_vendas_pagina(skip, _TAMANHO_PAGINA, loja_id, cliente_id, desde)
        vendas.extend(lote)

        if len(lote) < _TAMANHO_PAGINA:
            break

        skip += _TAMANHO_PAGINA

    return vendas


def listar_vendas_pagina(skip=0, limit=100, loja_id=None, cliente_id=None, desde=None):
    """Busca só uma página do histórico (mais recentes primeiro) -- pro
    'Carregar mais' da tela de Vendas, que não precisa (e não quer)
    trazer tudo de uma vez como listar_vendas() acima."""

    endpoint = f"/vendas/?skip={skip}&limit={limit}"
    if loja_id is not None:
        endpoint += f"&loja_id={loja_id}"
    if cliente_id is not None:
        endpoint += f"&cliente_id={cliente_id}"
    if desde is not None:
        endpoint += f"&data_inicio={desde.isoformat()}"

    response = get(endpoint)

    if response.status_code != 200:
        return []

    return response.json()


def cancelar_venda(venda_id, motivo=None):
    """Cancela a venda (DELETE /vendas/{id} no backend) -- devolve o
    estoque dos itens, estorna o pagamento no caixa/fiado e marca a
    venda como CANCELADA (ela continua no histórico, só não conta mais
    como faturamento)."""

    endpoint = f"/vendas/{venda_id}"

    if motivo:
        endpoint += f"?motivo={quote(motivo)}"

    return delete(endpoint)


def suspender_venda(itens, cliente_id=None, desconto=0):
    """Salva o carrinho atual como rascunho (Venda.status=ABERTA) pra
    retomar depois -- sem forma de pagamento, nao mexe em estoque nem
    caixa (ver VendaService.suspender no backend)."""

    dados = {
        "cliente_id": cliente_id,
        "desconto": desconto,
        "itens": [
            {
                "produto_id": item["id"],
                "quantidade": item["quantidade"],
                "valor_unitario": item["preco"],
            }
            for item in itens
        ],
    }

    return post(endpoint_com_loja("/vendas/suspender"), dados)


def listar_vendas_suspensas():

    response = get(endpoint_com_loja("/vendas/suspensas"))

    if response.status_code != 200:
        raise Exception(
            f"Falha ao carregar as vendas suspensas "
            f"(HTTP {response.status_code}): {response.text}"
        )

    return response.json()


def excluir_venda_suspensa(venda_id):
    return delete(f"/vendas/{venda_id}/suspensa")


def finalizar_venda(
    itens,
    forma_pagamento,
    cliente_id=None,
    desconto=0,
    observacao=None,
    data_vencimento=None,
    forma_pagamento_2=None,
    valor_forma_2=None,
    chave_idempotencia=None,
):

    dados = {
        "chave_idempotencia": chave_idempotencia,
        "cliente_id": cliente_id,
        "observacao": observacao,
        "desconto": desconto,
        "forma_pagamento": forma_pagamento,
        "forma_pagamento_2": forma_pagamento_2,
        "valor_forma_2": valor_forma_2,
        "data_vencimento": data_vencimento,
        "itens": [],
    }

    for item in itens:

        dados["itens"].append(
            {
                "produto_id": item["id"],
                "quantidade": item["quantidade"],
                "valor_unitario": item["preco"],
            }
        )

    return post(endpoint_com_loja("/vendas/"), dados)

def listar_vendas_periodo(data_inicio, data_fim, usuario_id=None, loja_id=None):
    """Todas as vendas entre as duas datas (date, inclusivas), mais
    recentes primeiro -- tela de Vendas. Varre as páginas como
    listar_vendas()."""

    filtros = f"&data_inicio={data_inicio.isoformat()}&data_fim={data_fim.isoformat()}"
    if usuario_id is not None:
        filtros += f"&usuario_id={usuario_id}"
    if loja_id is not None:
        filtros += f"&loja_id={loja_id}"

    vendas = []
    skip = 0

    while True:

        response = get(f"/vendas/?skip={skip}&limit={_TAMANHO_PAGINA}{filtros}")

        if response.status_code != 200:
            raise Exception("Não foi possível carregar as vendas.")

        lote = response.json()
        vendas.extend(lote)

        if len(lote) < _TAMANHO_PAGINA:
            break

        skip += _TAMANHO_PAGINA

    return vendas


def resumo_vendedores(data_inicio, data_fim, loja_id=None):
    """Total vendido por vendedora no período, já descontando
    devoluções (GET /vendas/resumo-vendedores)."""

    response = get(
        f"/vendas/resumo-vendedores?data_inicio={data_inicio.isoformat()}"
        f"&data_fim={data_fim.isoformat()}"
        + (f"&loja_id={loja_id}" if loja_id is not None else "")
    )

    if response.status_code != 200:
        raise Exception("Não foi possível carregar o resumo por vendedora.")

    return response.json()


def listar_devolucoes(venda_id):

    response = get(f"/vendas/{venda_id}/devolucoes")

    if response.status_code != 200:
        raise Exception("Não foi possível carregar as devoluções da venda.")

    return response.json()


def registrar_devolucao(venda_id, itens, forma_reembolso, motivo=None):
    """itens = [{"item_venda_id", "quantidade"}]. Devolve a resposta
    crua (quem chama mostra o "detail" do erro)."""

    return post(
        f"/vendas/{venda_id}/devolucoes",
        {
            "itens": itens,
            "forma_reembolso": forma_reembolso,
            "motivo": motivo,
        },
    )
