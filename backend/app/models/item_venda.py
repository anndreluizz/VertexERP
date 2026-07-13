from sqlalchemy import ForeignKey, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ItemVenda(Base):
    __tablename__ = "itens_venda"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    venda_id: Mapped[int] = mapped_column(
        ForeignKey("vendas.id")
    )

    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id")
    )

    quantidade: Mapped[int] = mapped_column(
        Integer
    )

    valor_unitario: Mapped[float] = mapped_column(
        Float
    )

    subtotal: Mapped[float] = mapped_column(
        Float
    )

    venda = relationship(
        "Venda",
        back_populates="itens"
    )

    produto = relationship("Produto")