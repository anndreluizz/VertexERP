from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ItemCompra(Base):

    __tablename__ = "itens_compra"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    compra_id: Mapped[int] = mapped_column(
        ForeignKey("compras.id"),
        index=True,
    )

    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id"),
        index=True,
    )

    quantidade: Mapped[int] = mapped_column(
        Integer,
    )

    valor_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
    )

    compra = relationship(
        "Compra",
        back_populates="itens",
    )

    produto = relationship(
        "Produto",
        back_populates="itens_compra",
    )