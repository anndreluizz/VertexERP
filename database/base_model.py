from datetime import datetime

from sqlalchemy import Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column


class BaseModelMixin:
    """
    Campos comuns para todas as tabelas do Vertex ERP
    """

    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )