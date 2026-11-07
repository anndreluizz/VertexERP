from decimal import Decimal
from sqlalchemy import Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class KitItem(Base):
    """Um componente de um kit/combo -- kit_id e produto_componente_id
    apontam pro mesmo Produto.id (um kit e' so' um Produto com
    eh_kit=True), entao os dois FKs precisam de foreign_keys explicito
    na relationship pra nao ficar ambiguo qual e' qual."""

    __tablename__ = "kit_itens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    kit_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id"),
        index=True,
        nullable=False,
    )

    produto_componente_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id"),
        index=True,
        nullable=False,
    )

    # quantos do componente entram em 1 unidade vendida do kit
    quantidade: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=1
    )

    componente = relationship(
        "Produto", foreign_keys=[produto_componente_id]
    )

    @property
    def produto_componente_nome(self):
        return self.componente.nome if self.componente else None
