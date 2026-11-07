from decimal import Decimal


def formatar_quantidade(valor, unidade: str | None = "UN") -> str:
    """2 -> "2"; KG/L -> "0,350 kg" (3 casas, igual balanca)."""

    valor = Decimal(valor or 0)
    unidade = (unidade or "UN").upper()

    if unidade in ("KG", "L"):
        return f"{valor:.3f}".replace(".", ",") + (" kg" if unidade == "KG" else " L")

    if valor == valor.to_integral_value():
        return str(int(valor))
    return f"{valor.normalize():f}".replace(".", ",")


def quantidade_por_unidade_valida(valor, unidade: str | None) -> bool:
    """Produto vendido por unidade nao aceita 0,5 -- so' KG/L fracionam."""

    return (unidade or "UN").upper() in ("KG", "L") or Decimal(valor) == Decimal(valor).to_integral_value()
