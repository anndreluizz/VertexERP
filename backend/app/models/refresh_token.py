from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RefreshToken(Base):
    """Sessão de longa duração emitida no login, guardada no aparelho do
    app mobile. O access_token (JWT) sozinho nunca poderia ser revogado
    antes de expirar naturalmente — este registro é o que permite
    "sessões abertas" e "logout remoto" de verdade (ver AuthService)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    usuario_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    token: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    dispositivo: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    expira_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    ultimo_uso_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    revogado: Mapped[bool] = mapped_column(Boolean, default=False)
