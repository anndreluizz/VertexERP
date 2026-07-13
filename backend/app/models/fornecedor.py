from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    String,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import Base


class Fornecedor(Base):
    __tablename__ = "fornecedores"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    razao_social: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    nome_fantasia: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    cnpj: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    telefone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    cidade: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    estado: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
    )

    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    # Relacionamentos
    compras = relationship(
        "Compra",
        back_populates="fornecedor",
        cascade="all, delete-orphan",
    )