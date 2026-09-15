from urllib.parse import quote

from services.api import get, post, delete, endpoint_com_loja

# a API nunca devolve mais que isso por chamada (ver vendas.py no
# backend) -- listar_vendas() varre todas as paginas por baixo dos
# panos, entao quem usa isso pra somar/analisar (dashboard, fiado,
# "mais vendidos", relatorios) continua vendo o historico completo,
# sem truncar silenciosamente em 100 registros.
_TAMANHO_PAGINA = 500


def listar_vendas():

    vendas = []
    skip = 0

    while True:

        lote = listar_vendas_pagina(skip, _TAMANHO_PAGINA)
        vendas.extend(lote)

        if len(lote) < _TAMANHO_PAGINA:
            break

        skip += _TAMANHO_PAGINA

    return vendas


def listar_vendas_pagina(skip=0, limit=100):
    """Busca só uma página do histórico (mais recentes primeiro) -- pro
    'Carregar mais' da tela de Vendas, que não precisa (e não quer)
    trazer tudo de uma vez como listar_vendas() acima."""

    response = get(f"/vendas/?skip={skip}&limit={limit}")

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