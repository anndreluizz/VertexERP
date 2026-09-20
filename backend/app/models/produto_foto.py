from sqlalchemy import Boolean, ForeignKey, Integer, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ProdutoFoto(Base):
    """Multiplas fotos por produto -- mesma estrategia de armazenamento
    (blob direto no Postgres) que Produto.foto ja usava, so' que numa
    tabela propria pra permitir mais de uma. Produto.foto continua
    existindo em paralelo por compatibilidade (ver migration que copia
    a foto unica existente pra cá com principal=True)."""

    __tablename__ = "produto_fotos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id"),
        index=True,
        nullable=False,
    )

    imagem: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    ordem: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    principal: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    produto = relationship("Produto", back_populates="fotos")
