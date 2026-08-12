from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class MovimentoFiado(Base):
    __tablename__ = "movimentos_fiado"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id")
    )

    venda_id: Mapped[int | None] = mapped_column(
        ForeignKey("vendas.id"),
        nullable=True
    )

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )

    tipo: Mapped[str] = mapped_column(
        String(20)
    )

    valor: Mapped[float] = mapped_column(
        Float
    )

    descricao: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    data: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    cliente = relationship("Cliente")

    venda = relationship("Venda")

    usuario = relationship("User")
