from datetime import datetime

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QInputDialog

from utils.formatacao import formatar_moeda
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
    """"3*789..." -> (3, "789..."); "0,350*789..." -> (0.35, ...) pra
    produto por peso; sem "*" -> (1, texto). So' aceita numero de 0 a
    9999 antes do "*" -- qualquer outra coisa e' tratada como parte do
    codigo/nome."""

    antes, separador, depois = texto.partition("*")
    antes = antes.strip()

    if separador and antes.isdigit() and 0 < int(antes) < 10000:
        return int(antes), depois.strip()

    if separador and antes.count(",") + antes.count(".") == 1:
        try:
            valor = round(float(antes.replace(",", ".")), 3)
        except ValueError:
            valor = 0
        if 0 < valor < 10000:
            return valor, depois.strip()

    return 1, texto


def pedir_peso(parent, produto, inicial=0.0):
    """Janela pra digitar o peso (kg) ou volume (L) lido na balanca.
    None = cancelou."""

    unidade = "kg" if (produto.get("unidade") or "").upper() == "KG" else "L"

    dlg = QInputDialog(parent)
    dlg.setLocale(QLocale(QLocale.Portuguese, QLocale.Brazil))
    dlg.setInputMode(QInputDialog.DoubleInput)
    dlg.setDoubleDecimals(3)
    dlg.setDoubleRange(0.001, 9999)
    dlg.setDoubleValue(float(inicial or 0))
    dlg.setWindowTitle("Peso" if unidade == "kg" else "Volume")
    dlg.setLabelText(
        f"{produto['nome']}\n"
        f"{formatar_moeda(produto['preco'])} / {unidade}\n\n"
        f"Quantidade ({unidade}):"
    )

    if not dlg.exec():
        return None
    return round(dlg.doubleValue(), 3)


def _baixar_foto_com_id(produto_id):
    """Roda na worker thread -- o id viaja junto com os bytes (nao da'
    pra usar closure como callback, ver services/worker.py)."""
    return produto_id, obter_foto_produto(produto_id)


def _parse_valor(texto):
    try:
        return max(0.0, float((texto or "").strip().replace(",", ".") or 0))
    except ValueError:
        return 0.0
