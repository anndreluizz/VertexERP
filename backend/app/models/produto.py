from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String,
    Boolean,
    ForeignKey,
    Index,
    Numeric,
    Integer,
    DateTime,
    LargeBinary,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base



class Produto(Base):
    __tablename__ = "produtos"

    # codigo/codigo_barras nao sao mais unique=True simples -- viram
    # unicos "por espaco" (ver __table_args__): globais entre si
    # (loja_id NULL) OU dentro da mesma loja (loja_id igual), nunca
    # comparados entre espacos diferentes. Isso deixa filial e matriz
    # usarem o mesmo codigo pra produtos diferentes (ver migration
    # 559952ab5045_produtos_exclusivos_por_loja).
    __table_args__ = (
        Index(
            "uq_produto_codigo_global", "codigo",
            unique=True, postgresql_where=text("loja_id IS NULL"),
        ),
        Index(
            "uq_produto_codigo_loja", "codigo", "loja_id",
            unique=True, postgresql_where=text("loja_id IS NOT NULL"),
        ),
        Index(
            "uq_produto_codigo_barras_global", "codigo_barras",
            unique=True, postgresql_where=text("loja_id IS NULL"),
        ),
        Index(
            "uq_produto_codigo_barras_loja", "codigo_barras", "loja_id",
            unique=True, postgresql_where=text("loja_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # nullable: produto sem loja e' "global" (visivel/vendavel em
    # qualquer loja, ver ProdutoRepository.listar); com loja_id
    # preenchido, fica EXCLUSIVO daquela loja -- diferente de
    # Cliente.loja_id, que so marca origem sem restringir nada.
    # resolver_loja_id() praticamente sempre resolve pra alguma loja,
    # entao na pratica todo produto cadastrado num terminal configurado
    # (filial, matriz, ...) nasce exclusivo dela.
    loja_id: Mapped[int | None] = mapped_column(
        ForeignKey("lojas.id"),
        index=True,
        nullable=True,
    )

    codigo: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    codigo_barras: Mapped[str] = mapped_column(
        String(50),
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

    preco_custo: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0
    )

    preco_venda: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
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

    foto: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True
    )

    favorito: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )

    @property
    def tem_foto(self) -> bool:
        return self.foto is not None

    itens_compra = relationship(
        "ItemCompra",
        back_populates="produto"
    )
    itens_venda = relationship("ItemVenda", back_populates="produto")
    movimentos_estoque = relationship(
        "MovimentoEstoque",
        back_populates="produto"
    )