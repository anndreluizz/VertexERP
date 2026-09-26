from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class MovimentoFiado(Base):
    __tablename__ = "movimentos_fiado"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id"),
        index=True,
        nullable=False
    )

    venda_id: Mapped[int | None] = mapped_column(
        ForeignKey("vendas.id", ondelete="SET NULL"),
        index=True,
        nullable=True
    )

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=False
    )

    tipo: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    forma_pagamento: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    valor: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    descricao: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    data: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    cliente = relationship(
        "Cliente",
        back_populates="movimentos_fiado"
    )

    venda = relationship("Venda")

    usuario = relationship("User")
