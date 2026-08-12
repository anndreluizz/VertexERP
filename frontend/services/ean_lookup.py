import requests

URL_BASE = "https://world.openfoodfacts.org/api/v2/product"

# A Open Food Facts exige um User-Agent identificando a aplicacao;
# sem isso, o servidor responde 403 Forbidden.
HEADERS = {
    "User-Agent": "VertexERP/1.0 (contato@vertexerp.local)"
}


def buscar_produto_externo(codigo_barras: str):
    """Consulta um banco de dados publico de produtos (Open Food Facts)
    pelo codigo de barras (EAN/UPC). Retorna None se nao encontrar."""

    try:
        response = requests.get(
            f"{URL_BASE}/{codigo_barras}.json",
            headers=HEADERS,
            timeout=6,
        )
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    dados = response.json()

    if dados.get("status") != 1:
        return None

    produto = dados.get("product", {})

    nome = (
        produto.get("product_name_pt")
        or produto.get("product_name")
        or produto.get("generic_name")
    )

    if not nome:
        return None

    imagem_url = (
        produto.get("image_front_small_url")
        or produto.get("image_small_url")
        or produto.get("image_url")
    )

    imagem_bytes = None

    if imagem_url:
        try:
            resposta_imagem = requests.get(
                imagem_url,
                headers=HEADERS,
                timeout=6,
            )
            if resposta_imagem.status_code == 200:
                imagem_bytes = resposta_imagem.content
        except requests.RequestException:
            imagem_bytes = None

    return {
        "nome": nome.strip(),
        "imagem_bytes": imagem_bytes,
    }
