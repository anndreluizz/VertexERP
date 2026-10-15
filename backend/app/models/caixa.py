from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import relationship
from sqlalchemy import DateTime, ForeignKey, Numeric, String
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
        default=datetime.now
    )

    data_fechamento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    saldo_inicial: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0
    )

    saldo_final: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="ABERTO"
    )

    valor_contado: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True
    )

    observacoes: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    # destino do dinheiro no fechamento: cofre/banco e retirada dos
    # socios (o resto fica de troco). None = caixa fechado antes disso
    valor_guardado: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True
    )

    valor_retirado: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True
    )

    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=True
    )

    # nullable pelo mesmo motivo de usuario_id -- caixas antigos nao
    # tem essa informacao (backfill pra Matriz na migracao)
    loja_id: Mapped[int | None] = mapped_column(
        ForeignKey("lojas.id"),
        index=True,
        nullable=True
    )

    movimentos = relationship(
        "MovimentoCaixa",
        back_populates="caixa",
        cascade="all, delete-orphan"
    )