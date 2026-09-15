from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ItemVenda(Base):
    __tablename__ = "itens_venda"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    venda_id: Mapped[int] = mapped_column(
        ForeignKey("vendas.id"),
        index=True,
    )

    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id"),
        index=True,
    )

    quantidade: Mapped[int] = mapped_column(
        Integer
    )

    valor_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2)
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2)
    )

    venda = relationship(
        "Venda",
        back_populates="itens"
    )

    produto = relationship("Produto", back_populates="itens_venda")