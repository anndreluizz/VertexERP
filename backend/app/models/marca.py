from datetime import datetime

from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Marca(Base):
    __tablename__ = "marcas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    nome: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    descricao: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )

    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
