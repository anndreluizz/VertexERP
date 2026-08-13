from services.api import get, post, put, delete

# a API nunca devolve mais que isso por chamada (ver clientes.py no
# backend) -- listar_clientes() varre todas as paginas por baixo dos
# panos, entao pra quem chama continua parecendo uma lista so, so que
# agora sem truncar silenciosamente em 100 registros.
_TAMANHO_PAGINA = 500


def listar_clientes():

    clientes = []
    pagina = 0

    while True:

        response = get(
            f"/clientes/?skip={pagina * _TAMANHO_PAGINA}"
            f"&limit={_TAMANHO_PAGINA}"
        )

        if response.status_code != 200:
            break

        lote = response.json()
        clientes.extend(lote)

        if len(lote) < _TAMANHO_PAGINA:
            break

        pagina += 1

    return clientes


def cadastrar_cliente(dados):

    return post("/clientes/", dados)


def atualizar_cliente(cliente_id, dados):

    return put(f"/clientes/{cliente_id}", dados)


def excluir_cliente(cliente_id):

    return delete(f"/clientes/{cliente_id}")


def reativar_cliente(cliente_id):

    return post(f"/clientes/{cliente_id}/reativar", {})


def enviar_whatsapp_texto(cliente_id, texto):
    """Manda uma mensagem de texto livre pro cliente via WhatsApp
    (extrato completo, cobrança, saldo devedor, haver, cadastro --
    ver menu 'WhatsApp ▾' da ficha do cliente)."""

    return post(f"/clientes/{cliente_id}/whatsapp", {"texto": texto})


def obter_foto_cliente(cliente_id):

    response = get(f"/clientes/{cliente_id}/foto")

    if response.status_code != 200:
        return None

    return response.content


def listar_observacoes_cliente(cliente_id):

    response = get(f"/clientes/{cliente_id}/observacoes")

    if response.status_code != 200:
        return []

    return response.json()


def criar_observacao_cliente(cliente_id, texto):

    return post(f"/clientes/{cliente_id}/observacoes", {"texto": texto})


def excluir_observacao_cliente(cliente_id, observacao_id):

    return delete(f"/clientes/{cliente_id}/observacoes/{observacao_id}")
