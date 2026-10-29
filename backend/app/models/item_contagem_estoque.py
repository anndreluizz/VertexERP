from decimal import Decimal
from sqlalchemy import Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ItemContagemEstoque(Base):
    __tablename__ = "itens_contagem_estoque"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    contagem_id: Mapped[int] = mapped_column(
        ForeignKey("contagens_estoque.id"),
        index=True,
        nullable=False,
    )

    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id"),
        index=True,
        nullable=False,
    )

    # snapshot da quantidade NESSA loja no momento em que a contagem foi
    # aberta -- congelado de proposito, pra a divergencia comparar com o
    # que o sistema dizia ter na hora da contagem, nao com o estoque
    # atual (que pode ter mudado por vendas no meio do processo).
    quantidade_sistema: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    quantidade_contada: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )

    contagem = relationship("ContagemEstoque", back_populates="itens")

    produto = relationship("Produto")

    @property
    def produto_nome(self):
        return self.produto.nome if self.produto else None
