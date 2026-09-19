from datetime import datetime

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Numeric,
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

    # percentual aplicado sobre o custo pra sugerir preco_venda na
    # importacao de NF-e (ex.: 15.00 = +15%) -- server_default pra nao
    # quebrar fornecedores ja existentes em producao (ver migration).
    margem_padrao: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0"),
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    # Relacionamentos
    # SEM cascade delete-orphan de proposito: excluir() e' soft-delete
    # (ativo=False), nunca remove a linha -- um cascade aqui so' faria
    # sentido se algum dia alguem reintroduzir hard-delete, e nesse caso
    # apagaria o historico de Compras junto, o que nunca e' o que se quer.
    compras = relationship(
        "Compra",
        back_populates="fornecedor",
    )