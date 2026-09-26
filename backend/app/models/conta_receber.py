from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ContaReceber(Base):
    __tablename__ = "contas_receber"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id"),
        index=True,
    )

    venda_id: Mapped[int | None] = mapped_column(
        ForeignKey("vendas.id"),
        index=True,
        nullable=True
    )

    # nullable pelo mesmo motivo das outras entidades com loja_id novo
    # -- contas antigas nao tem essa informacao (backfill na migracao)
    loja_id: Mapped[int | None] = mapped_column(
        ForeignKey("lojas.id"),
        index=True,
        nullable=True
    )

    data_emissao: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    data_vencimento: Mapped[datetime] = mapped_column(
        DateTime
    )

    data_recebimento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    valor: Mapped[Decimal] = mapped_column(
        Numeric(12, 2)
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