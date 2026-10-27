from decimal import Decimal

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


class Schema(BaseModel):
    """Base de todos os schemas: mantem o JSON igual ao da era pydantic v1.

    - from_attributes: aceita objeto ORM em model_validate (era orm_mode)
    - coerce_numbers_to_str: 123 vira "123" num campo str (v1 fazia sozinho)
    - Decimal sai como numero, nao string: frontend e app fazem conta com ele
    """

    # ponytail: json_encoders e' deprecado na v2 mas segue funcionando;
    # trocar por PlainSerializer num tipo Dinheiro se sair numa v2.x futura
    model_config = ConfigDict(
        from_attributes=True,
        coerce_numbers_to_str=True,
        json_encoders={Decimal: float},
    )


def _quantidade_json(valor: Decimal) -> int | float:
    # 5.000 sai 5 (cliente antigo que le int nao quebra), 0.350 sai 0.35
    return int(valor) if valor == valor.to_integral_value() else float(valor)


# quantidade/estoque: inteiro em produto por unidade, fracionado em KG/L
Quantidade = Annotated[Decimal, PlainSerializer(_quantidade_json, when_used="json")]
QuantidadePositiva = Annotated[
    Decimal, Field(gt=0, decimal_places=3),
    PlainSerializer(_quantidade_json, when_used="json"),
]
