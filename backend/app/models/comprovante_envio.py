from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ComprovanteEnvio(Base):
    """Registro de auditoria de cada tentativa de envio do comprovante
    (WhatsApp ou e-mail) -- nunca apagado, nem quando o envio falha:
    o histórico da falha também importa pra quem for conferir depois
    se o cliente recebeu ou não."""

    __tablename__ = "comprovante_envios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    venda_id: Mapped[int] = mapped_column(
        ForeignKey("vendas.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    # WHATSAPP ou EMAIL
    canal: Mapped[str] = mapped_column(String(20), nullable=False)

    # numero de telefone (WHATSAPP) ou endereco de e-mail (EMAIL)
    destino: Mapped[str] = mapped_column(String(150), nullable=False)

    # ENVIADO ou FALHOU
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    erro: Mapped[str | None] = mapped_column(String(255), nullable=True)

    data: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    venda = relationship("Venda")
    usuario = relationship("User")

    @property
    def usuario_nome(self) -> str | None:
        return self.usuario.nome if self.usuario else None
