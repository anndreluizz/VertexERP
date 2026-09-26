from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ContagemEstoque(Base):
    __tablename__ = "contagens_estoque"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    loja_id: Mapped[int] = mapped_column(
        ForeignKey("lojas.id"),
        index=True,
        nullable=False,
    )

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    # ABERTA -> FINALIZADA (gera os ajustes) ou CANCELADA (descarta),
    # mesmo padrao de status livre em string usado por Caixa/Venda.
    status: Mapped[str] = mapped_column(String(20), default="ABERTA")

    observacao: Mapped[str | None] = mapped_column(String(255), nullable=True)

    criado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )

    finalizado_em: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    itens = relationship(
        "ItemContagemEstoque",
        back_populates="contagem",
        cascade="all, delete-orphan",
    )

    usuario = relationship("User")
