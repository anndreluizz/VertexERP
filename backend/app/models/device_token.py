from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    usuario_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    token: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    plataforma: Mapped[str] = mapped_column(
        String(20),
        default="ANDROID",
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
