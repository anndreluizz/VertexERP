from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Compra(Base):

    __tablename__ = "compras"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    fornecedor_id: Mapped[int] = mapped_column(
        ForeignKey("fornecedores.id"),
        index=True,
    )

    data: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    valor_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
    )

    observacao: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="FINALIZADA",
    )

    forma_pagamento: Mapped[str] = mapped_column(
        String(20),
        default="AVISTA",
    )

    data_vencimento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    cancelado_em: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    fornecedor = relationship(
        "Fornecedor",
        back_populates="compras",
    )

    itens = relationship(
        "ItemCompra",
        back_populates="compra",
        cascade="all, delete-orphan",
    )