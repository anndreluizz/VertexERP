from datetime import datetime

from sqlalchemy.orm import relationship
from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Caixa(Base):
    __tablename__ = "caixa"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    data_abertura: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    data_fechamento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    saldo_inicial: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    saldo_final: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="ABERTO"
    )

    valor_contado: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    observacoes: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    movimentos = relationship(
        "MovimentoCaixa",
        back_populates="caixa",
        cascade="all, delete-orphan"
    )