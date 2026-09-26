from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Loja(Base):
    __tablename__ = "lojas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    nome: Mapped[str] = mapped_column(String(100), nullable=False)

    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )
