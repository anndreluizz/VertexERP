from services.api import get, post, put, delete, endpoint_com_loja


_TAMANHO_PAGINA = 500


def listar_contas_pagar(loja_id=None):

    # loja_id aqui e' o filtro escolhido no combo da tela (ver
    # ContasPagar._carregar_combo_lojas), diferente do loja_id fixo do
    # terminal usado em endpoint_com_loja() pra escrita -- por isso
    # nao usa esse helper aqui. Varre todas as paginas: o backend
    # devolve no maximo 500 por vez, e com parcelas e contas fixas a
    # lista passa disso (antes vinham so' as 100 primeiras).
    filtro = f"&loja_id={loja_id}" if loja_id is not None else ""

    contas = []
    skip = 0

    while True:

        response = get(f"/contas-pagar/?skip={skip}&limit={_TAMANHO_PAGINA}{filtro}")

        if response.status_code != 200:
            return contas

        lote = response.json()
        contas.extend(lote)

        if len(lote) < _TAMANHO_PAGINA:
            return contas

        skip += _TAMANHO_PAGINA


def cadastrar_conta_parcelada(dados, numero_parcelas):
    """dados["valor"] = valor de UMA parcela; as parcelas vencem no
    mesmo dia dos meses seguintes (ver backend criar_parcelado)."""

    return post(
        endpoint_com_loja("/contas-pagar/parcelado"),
        {**dados, "numero_parcelas": numero_parcelas},
    )


def cadastrar_conta_fixa(dados):
    """Conta que se repete todo mês -- dados: descricao, valor,
    primeiro_vencimento (aaaa-mm-dd), valor_variavel, categoria,
    centro_custo, plano_conta_id, observacao."""

    return post(endpoint_com_loja("/contas-recorrentes/"), dados)


def listar_contas_fixas():

    response = get("/contas-recorrentes/")

    if response.status_code != 200:
        raise Exception("Não foi possível carregar as contas fixas.")

    return response.json()


def atualizar_conta_fixa(recorrente_id, dados):

    return put(f"/contas-recorrentes/{recorrente_id}", dados)


def parar_conta_fixa(recorrente_id):

    return delete(f"/contas-recorrentes/{recorrente_id}")


def cadastrar_conta_pagar(dados):

    return post(endpoint_com_loja("/contas-pagar/"), dados)


def atualizar_conta_pagar(conta_id, dados):

    return put(f"/contas-pagar/{conta_id}", dados)


def excluir_conta_pagar(conta_id):

    return delete(f"/contas-pagar/{conta_id}")


def pagar_conta_pagar(
    conta_id,
    forma_pagamento=None,
    comprovante_base64=None,
    comprovante_nome=None,
    comprovante_tipo=None,
):

    dados = {}

    if forma_pagamento:
        dados["forma_pagamento"] = forma_pagamento

    if comprovante_base64:
        dados["comprovante_base64"] = comprovante_base64
        dados["comprovante_nome"] = comprovante_nome
        dados["comprovante_tipo"] = comprovante_tipo

    return post(f"/contas-pagar/{conta_id}/pagar", dados)


def obter_documento_conta_pagar(conta_id):

    return get(f"/contas-pagar/{conta_id}/documento")


def remover_documento_conta_pagar(conta_id):

    return delete(f"/contas-pagar/{conta_id}/documento")


def obter_comprovante_pagamento_conta_pagar(conta_id):

    return get(f"/contas-pagar/{conta_id}/comprovante-pagamento")


def ler_boleto(codigo=None, pdf_base64=None):
    """Lê o boleto (código bipado/digitado ou PDF) -- devolve a resposta
    crua: valor, vencimento, banco, fornecedor sugerido e se ele já foi
    lançado (ver POST /contas-pagar/ler-boleto). Não grava nada."""

    return post("/contas-pagar/ler-boleto", {"codigo": codigo, "pdf_base64": pdf_base64})


def listar_parcelamento(parcelamento_id):

    response = get(f"/contas-pagar/parcelamento/{parcelamento_id}")

    if response.status_code != 200:
        raise Exception("Não foi possível carregar as parcelas.")

    return response.json()


def cancelar_parcelas_restantes(parcelamento_id):

    return post(f"/contas-pagar/parcelamento/{parcelamento_id}/cancelar-restantes", {})
