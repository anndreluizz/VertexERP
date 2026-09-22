from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Notificacao(Base):
    """Uma linha por destinatario (NotificacaoService.enviar_para_admins
    faz fan-out pra cada admin) -- assim "lida" e' um estado por
    usuario, nao compartilhado. E' a mesma chamada que ja dispara push
    via Firebase (ver NotificacaoService) que agora tambem persiste
    aqui, pra existir uma central de notificacoes no desktop (que nao
    tem device token/push nenhum, so' o mobile tem)."""

    __tablename__ = "notificacoes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )

    titulo: Mapped[str] = mapped_column(String(150))

    corpo: Mapped[str] = mapped_column(String(500))

    lida: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )
