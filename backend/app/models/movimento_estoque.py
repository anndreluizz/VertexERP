from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class MovimentoEstoque(Base):
    __tablename__ = "movimentos_estoque"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id")
    )

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )

    tipo: Mapped[str] = mapped_column(
        String(20)
    )

    quantidade: Mapped[int] = mapped_column(
        Integer
    )

    motivo: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    data: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    produto = relationship("Produto")

    usuario = relationship("User")
