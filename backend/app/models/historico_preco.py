from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class HistoricoPreco(Base):
    __tablename__ = "historico_precos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id"),
        index=True,
        nullable=False,
    )

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    preco_custo_anterior: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    preco_custo_novo: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    preco_venda_anterior: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    preco_venda_novo: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    data: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usuario = relationship("User")

    @property
    def usuario_nome(self) -> str | None:
        return self.usuario.nome if self.usuario else None
