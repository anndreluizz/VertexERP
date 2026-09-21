from urllib.parse import quote

from services.api import get, post, delete, endpoint_com_loja

# a API nunca devolve mais que isso por chamada (ver vendas.py no
# backend) -- listar_vendas() varre todas as paginas por baixo dos
# panos, entao quem usa isso pra somar/analisar (dashboard, fiado,
# "mais vendidos", relatorios) continua vendo o historico completo,
# sem truncar silenciosamente em 100 registros.
_TAMANHO_PAGINA = 500


def listar_vendas(loja_id=None):
    """loja_id=None busca de TODAS as lojas de propósito -- usado pra
    montar o histórico de compras de um cliente (ficha_cliente.py,
    clientes.py), que não é restrito por loja (ver Cliente.loja_id).
    Quem precisa da visão de uma loja só (dashboard.py, visao_geral.py)
    passa o loja_id do terminal explicitamente."""

    vendas = []
    skip = 0

    while True:

        lote = listar_vendas_pagina(skip, _TAMANHO_PAGINA, loja_id)
        vendas.extend(lote)

        if len(lote) < _TAMANHO_PAGINA:
            break

        skip += _TAMANHO_PAGINA

    return vendas


def listar_vendas_pagina(skip=0, limit=100, loja_id=None):
    """Busca só uma página do histórico (mais recentes primeiro) -- pro
    'Carregar mais' da tela de Vendas, que não precisa (e não quer)
    trazer tudo de uma vez como listar_vendas() acima."""

    endpoint = f"/vendas/?skip={skip}&limit={limit}"
    if loja_id is not None:
        endpoint += f"&loja_id={loja_id}"

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
):

    dados = {
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