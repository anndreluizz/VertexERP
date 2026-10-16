from datetime import datetime

from services.produto_service import (
    obter_foto_produto,
)


ATALHOS_PADRAO = {"busca": "F1", "cadastro_rapido": "F4", "cancelar": "Esc"}


LARGURA_PAINEL_RESUMO = 340


_CORES_MONOGRAMA = [
    "#2563EB", "#16A34A", "#D97706", "#DB2777", "#7C3AED", "#0891B2",
]


def _parse_data(texto):
    try:
        return datetime.fromisoformat(texto)
    except (ValueError, TypeError):
        return None


def _separar_multiplicador(texto):
    """"3*789..." -> (3, "789..."); sem "*" -> (1, texto). So' aceita
    inteiro de 1 a 9999 antes do "*" -- qualquer outra coisa e' tratada
    como parte do codigo/nome."""

    antes, separador, depois = texto.partition("*")

    if separador and antes.strip().isdigit() and 0 < int(antes) < 10000:
        return int(antes), depois.strip()

    return 1, texto


def _baixar_foto_com_id(produto_id):
    """Roda na worker thread -- o id viaja junto com os bytes (nao da'
    pra usar closure como callback, ver services/worker.py)."""
    return produto_id, obter_foto_produto(produto_id)


def _parse_valor(texto):
    try:
        return max(0.0, float((texto or "").strip().replace(",", ".") or 0))
    except ValueError:
        return 0.0
