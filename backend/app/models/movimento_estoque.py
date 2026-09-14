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
        ForeignKey("produtos.id"),
        index=True,
        nullable=False
    )

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=False
    )

    loja_id: Mapped[int | None] = mapped_column(
        ForeignKey("lojas.id"),
        index=True,
        nullable=True
    )

    tipo: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    quantidade: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    motivo: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    data: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    produto = relationship(
        "Produto",
        back_populates="movimentos_estoque"
    )

    usuario = relationship("User")
