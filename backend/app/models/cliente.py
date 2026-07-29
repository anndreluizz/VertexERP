from datetime import datetime

from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    nome: Mapped[str] = mapped_column(String(150), nullable=False)

    cpf_cnpj: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        nullable=True
    )

    telefone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    email: Mapped[str] = mapped_column(
        String(150),
        nullable=True
    )

    endereco: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )

    cidade: Mapped[str] = mapped_column(
        String(100),
        nullable=True
    )

    estado: Mapped[str] = mapped_column(
        String(2),
        nullable=True
    )

    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    vendas = relationship(
        "Venda",
        back_populates="cliente"
    )

    movimentos_fiado = relationship(
        "MovimentoFiado",
        back_populates="cliente"
    )