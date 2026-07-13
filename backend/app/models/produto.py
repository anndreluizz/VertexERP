from datetime import datetime

from sqlalchemy import String, Boolean, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base



class Produto(Base):
    __tablename__ = "produtos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    codigo: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False
    )

    codigo_barras: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=True
    )

    nome: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    descricao: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )

    categoria: Mapped[str] = mapped_column(
        String(100),
        nullable=True
    )

    preco_custo: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    preco_venda: Mapped[float] = mapped_column(
        Float,
        default=0
    )

    estoque: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    estoque_minimo: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    unidade: Mapped[str] = mapped_column(
        String(10),
        default="UN"
    )

    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    itens_compra = relationship(
        "ItemCompra",
        back_populates="produto"
    )
    itens_venda = relationship("ItemVenda")