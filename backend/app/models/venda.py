from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Venda(Base):
    __tablename__ = "vendas"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id"),
        nullable=True
    )

    data: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    valor_total: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    desconto: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    observacao: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="FINALIZADA"
    )

    # NOVO
    forma_pagamento: Mapped[str] = mapped_column(
        String(20),
        default="AVISTA"
    )

    # NOVO
    data_vencimento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    cliente = relationship(
        "Cliente",
        back_populates="vendas"
    )

    itens = relationship(
        "ItemVenda",
        back_populates="venda",
        cascade="all, delete-orphan"
    )