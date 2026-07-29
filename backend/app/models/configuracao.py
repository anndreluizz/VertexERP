from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Configuracao(Base):
    __tablename__ = "configuracoes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    nome_loja: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    cnpj_cpf: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    endereco: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    telefone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    pix_chave: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    pix_nome: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    pix_cidade: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    logo_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
