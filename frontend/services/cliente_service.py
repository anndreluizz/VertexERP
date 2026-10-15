from services.api import get, post, put, delete, endpoint_com_loja

# a API nunca devolve mais que isso por chamada (ver clientes.py no
# backend) -- listar_clientes() varre todas as paginas por baixo dos
# panos, entao pra quem chama continua parecendo uma lista so, so que
# agora sem truncar silenciosamente em 100 registros.
_TAMANHO_PAGINA = 500


def listar_clientes(loja_id=None):

    # loja_id aqui e' o filtro escolhido na tela (combo "Todas as
    # lojas"/uma loja especifica), diferente do loja_id fixo do
    # terminal usado em endpoint_com_loja() pra escrita -- por isso
    # nao usa esse helper aqui (mesmo padrao de listar_contas_pagar)
    clientes = []
    pagina = 0

    while True:

        endpoint = (
            f"/clientes/?skip={pagina * _TAMANHO_PAGINA}"
            f"&limit={_TAMANHO_PAGINA}"
        )
        if loja_id is not None:
            endpoint += f"&loja_id={loja_id}"

        response = get(endpoint)

        if response.status_code != 200:
            # mesmo raciocinio de ProdutoService.listar_produtos: so' a
            # 1a pagina falhando vira erro de verdade, pra "erro de
            # rede" nao parecer "zero clientes cadastrados" pra tela
            if pagina == 0:
                raise Exception(
                    "Não foi possível carregar os clientes "
                    f"(servidor respondeu {response.status_code})."
                )
            break

        lote = response.json()
        clientes.extend(lote)

        if len(lote) < _TAMANHO_PAGINA:
            break

        pagina += 1

    return clientes


def cadastrar_cliente(dados):

    return post(endpoint_com_loja("/clientes/"), dados)


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


def exportar_dados_lgpd(cliente_id):
    """Todos os dados pessoais guardados sobre o cliente, numa
    resposta só -- atende um pedido de acesso/portabilidade da LGPD
    (só admin, ver backend/app/api/v1/clientes.py)."""

    return get(f"/clientes/{cliente_id}/dados-lgpd")


def remover_dados_lgpd(cliente_id):
    """Direito ao esquecimento da LGPD -- apaga os dados pessoais do
    cliente, mantendo o histórico de vendas/fiado (só admin, ação
    irreversível)."""

    return delete(f"/clientes/{cliente_id}/dados-lgpd")


def negativar_cliente(cliente_id, motivo):
    """Bloqueia o cliente (nao compra nada) e baixa a divida como perda.
    So' admin -- o backend recusa os outros."""

    response = post(f"/clientes/{cliente_id}/negativar", {"motivo": motivo})
    if response.status_code != 200:
        raise Exception(_detalhe(response))
    return response.json()


def desbloquear_cliente(cliente_id):

    response = post(f"/clientes/{cliente_id}/desbloquear", {})
    if response.status_code != 200:
        raise Exception(_detalhe(response))
    return response.json()


def _detalhe(response):
    try:
        return response.json().get("detail") or response.text
    except ValueError:
        return response.text
