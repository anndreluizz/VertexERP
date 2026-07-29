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

    # pagamento dividido (no maximo 2 formas por venda): a forma
    # principal usa valor_total - valor_forma_2, e essa segunda forma
    # cobre o restante — usado pra casos tipo "parte dinheiro parte
    # pix" ou "entrada + resto no fiado"
    forma_pagamento_2: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    valor_forma_2: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # NOVO
    data_vencimento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    data_fechamento: Mapped[datetime | None] = mapped_column(
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