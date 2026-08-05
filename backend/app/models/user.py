from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    nome: Mapped[str] = mapped_column(String(100), nullable=False)

    email: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True,
        nullable=False
    )

    senha: Mapped[str] = mapped_column(String(255), nullable=False)

    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    # Coluna preparada pra 2FA (ainda sem fluxo de verificacao completo
    # no app) -- guarda espaco no schema pra nao precisar de outra
    # migration quando o segundo fator entrar de verdade.
    dois_fatores_ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )