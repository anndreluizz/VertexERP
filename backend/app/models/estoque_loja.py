from decimal import Decimal
from sqlalchemy import Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class EstoqueLoja(Base):
    """Quantidade de um produto numa loja especifica -- o catalogo
    (Produto: nome/codigo/preco) continua unico e compartilhado entre
    lojas, so a quantidade fisica em estoque e o minimo de alerta viram
    por loja. `Produto.estoque`/`estoque_minimo` continuam existindo
    por enquanto (nao remover ainda -- varios services/telas leem
    direto de la); a migracao pra usar EstoqueLoja como fonte de
    verdade acontece nos proximos passos, endpoint por endpoint."""

    __tablename__ = "estoque_lojas"
    __table_args__ = (
        UniqueConstraint("produto_id", "loja_id", name="uq_estoque_loja_produto"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id"),
        index=True,
        nullable=False
    )

    loja_id: Mapped[int] = mapped_column(
        ForeignKey("lojas.id"),
        index=True,
        nullable=False
    )

    quantidade: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)

    estoque_minimo: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)

    produto = relationship("Produto")
    loja = relationship("Loja")
