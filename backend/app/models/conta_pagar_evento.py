from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ContaPagarEvento(Base):
    """Linha do tempo de auditoria de uma despesa -- quem fez o que e
    quando. So cresce (nunca é editado/apagado), por isso não tem
    updated_em nem soft-delete: cada linha é um fato que já aconteceu.
    """

    __tablename__ = "contas_pagar_eventos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    conta_pagar_id: Mapped[int] = mapped_column(
        ForeignKey("contas_pagar.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # CRIADA, DOCUMENTO_ANEXADO, PAGA, COMPROVANTE_ANEXADO,
    # COMPROVANTE_TROCADO, CANCELAMENTO_SOLICITADO, CANCELADA
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)

    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=True,
    )

    # nome do aparelho/plataforma que originou a acao (ex.: "Android",
    # "Desktop") -- opcional, nem toda origem informa isso hoje.
    dispositivo: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    detalhes: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    data: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    usuario = relationship("User")

    @property
    def usuario_nome(self) -> str | None:
        return self.usuario.nome if self.usuario else None
