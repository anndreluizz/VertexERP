from datetime import date, datetime

from sqlalchemy import String, Boolean, DateTime, Date, Float, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    nome: Mapped[str] = mapped_column(String(150), nullable=False)

    cpf_cnpj: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        nullable=True
    )

    telefone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    email: Mapped[str] = mapped_column(
        String(150),
        nullable=True
    )

    endereco: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )

    cidade: Mapped[str] = mapped_column(
        String(100),
        nullable=True
    )

    estado: Mapped[str] = mapped_column(
        String(2),
        nullable=True
    )

    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    data_nascimento: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    limite_credito: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    foto: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True
    )

    # Quando foi mandado o ultimo lembrete de fiado parado via
    # WhatsApp -- evita mandar o mesmo aviso todo dia enquanto o
    # cliente nao paga (ver whatsapp_lembrete_service.py).
    whatsapp_fiado_avisado_em: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    @property
    def tem_foto(self) -> bool:
        return self.foto is not None

    vendas = relationship(
        "Venda",
        back_populates="cliente"
    )

    movimentos_fiado = relationship(
        "MovimentoFiado",
        back_populates="cliente"
    )

    observacoes = relationship(
        "ClienteObservacao",
        back_populates="cliente",
        cascade="all, delete-orphan",
        order_by="ClienteObservacao.criado_em.desc()",
    )