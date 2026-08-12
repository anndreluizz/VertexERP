from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class MovimentoCaixa(Base):
    __tablename__ = "movimentos_caixa"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    caixa_id: Mapped[int] = mapped_column(
        ForeignKey("caixa.id"),
        nullable=False
    )

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    venda_id: Mapped[int | None] = mapped_column(
        ForeignKey("vendas.id", ondelete="SET NULL"),
        nullable=True
    )

    data: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    tipo: Mapped[str] = mapped_column(
        String(20)
    )

    descricao: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    valor: Mapped[float] = mapped_column(
        Float
    )

    caixa = relationship(
        "Caixa",
        back_populates="movimentos"
    )

    usuario = relationship(
        "User"
    )

    venda = relationship(
        "Venda"
    )