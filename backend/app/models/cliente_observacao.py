from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ClienteObservacao(Base):
    __tablename__ = "cliente_observacoes"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=False
    )

    texto: Mapped[str] = mapped_column(
        String(1000),
        nullable=False
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )

    cliente = relationship(
        "Cliente",
        back_populates="observacoes"
    )

    usuario = relationship("User")
