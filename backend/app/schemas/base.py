from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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
