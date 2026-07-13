from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column


class AuditMixin:
    """
    Auditoria do sistema
    """

    criado_por: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    atualizado_por: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )