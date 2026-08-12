from sqlalchemy import Float, ForeignKey, Integer
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
    )

    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id"),
    )

    quantidade: Mapped[int] = mapped_column(
        Integer,
    )

    valor_unitario: Mapped[float] = mapped_column(
        Float,
    )

    subtotal: Mapped[float] = mapped_column(
        Float,
    )

    compra = relationship(
        "Compra",
        back_populates="itens",
    )

    produto = relationship(
        "Produto",
        back_populates="itens_compra",
    )