from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ContaReceber(Base):
    __tablename__ = "contas_receber"

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

    data_emissao: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    data_vencimento: Mapped[datetime] = mapped_column(
        DateTime
    )

    data_recebimento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    valor: Mapped[float] = mapped_column(
        Float
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDENTE"
    )

    observacao: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    cliente = relationship("Cliente")
    venda = relationship("Venda")