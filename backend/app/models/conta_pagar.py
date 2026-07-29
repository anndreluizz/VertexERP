from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import Base


class ContaPagar(Base):

    __tablename__ = "contas_pagar"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    fornecedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("fornecedores.id"),
        nullable=True,
    )

    compra_id: Mapped[int | None] = mapped_column(
        ForeignKey("compras.id"),
        nullable=True,
    )

    data_emissao: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    data_vencimento: Mapped[datetime]

    data_pagamento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    valor: Mapped[float]

    descricao: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    categoria: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    observacao: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDENTE",
    )

    numero_boleto: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    fornecedor = relationship(
        "Fornecedor"
    )