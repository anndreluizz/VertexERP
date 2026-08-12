from datetime import datetime

from sqlalchemy.orm import relationship
from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database.base import Base


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
    movimentos = relationship(
        "MovimentoCaixa",
        back_populates="caixa",
        cascade="all, delete-orphan"
    )