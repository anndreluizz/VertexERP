from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    String,
    Boolean,
    ForeignKey,
    Index,
    Numeric,
    Integer,
    Date,
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

    marca_id: Mapped[int | None] = mapped_column(
        ForeignKey("marcas.id"),
        index=True,
        nullable=True,
    )

    colecao: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    cor: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    tamanho: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # variacao (cor/tamanho) de outro produto -- so' 1 nivel, ver
    # ProdutoService.criar (bloqueia variacao-de-variacao). Sem
    # relationship ORM de proposito (self-referencial em duas direcoes
    # complicaria mais do que ajuda); quem precisa das variacoes de um
    # produto usa ProdutoRepository.listar_variacoes.
    produto_pai_id: Mapped[int | None] = mapped_column(
        ForeignKey("produtos.id"),
        index=True,
        nullable=True,
    )

    preco_custo: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0
    )

    preco_venda: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0
    )

    # preco_promocional so' vale de fato dentro de [promocao_inicio,
    # promocao_fim] (ver em_promocao/preco_efetivo abaixo) -- ambas as
    # datas sao opcionais: sem elas, uma promocao com preco preenchido
    # fica valendo indefinidamente ate alguem apagar o preco.
    preco_promocional: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    promocao_inicio: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    promocao_fim: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    estoque: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        default=0
    )

    estoque_minimo: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
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
        default=datetime.now
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

    # kit/combo: vendido como 1 produto, mas o estoque baixado/devolvido
    # na venda e' o dos componentes (ver KitItem) -- o kit em si nunca
    # tem Produto.estoque/EstoqueLoja proprio debitado.
    eh_kit: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )

    # vitrine virtual (site da loja, ver app/api/v1/vitrine.py): so'
    # aparece la' produto ativo com vitrine_publicar=True; destaque
    # escolhe o que vai no banner/secao "Destaques".
    vitrine_publicar: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )

    vitrine_destaque: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )

    @property
    def tem_foto(self) -> bool:
        return self.foto is not None

    @property
    def em_promocao(self) -> bool:
        if self.preco_promocional is None:
            return False

        hoje = date.today()

        if self.promocao_inicio and hoje < self.promocao_inicio:
            return False

        if self.promocao_fim and hoje > self.promocao_fim:
            return False

        return True

    @property
    def preco_efetivo(self) -> Decimal:
        return self.preco_promocional if self.em_promocao else self.preco_venda

    # foto (LargeBinary acima) continua existindo por compatibilidade
    # com o que ja le GET /produtos/{id}/foto -- fotos, o novo suporte
    # a multiplas fotos, e' a fonte de verdade daqui pra frente (ver
    # migration que copia Produto.foto pra uma linha aqui com
    # principal=True na hora de introduzir esse model).
    fotos = relationship(
        "ProdutoFoto",
        back_populates="produto",
        cascade="all, delete-orphan",
        order_by="ProdutoFoto.ordem",
    )

    marca = relationship("Marca")

    itens_compra = relationship(
        "ItemCompra",
        back_populates="produto"
    )
    itens_venda = relationship("ItemVenda", back_populates="produto")
    movimentos_estoque = relationship(
        "MovimentoEstoque",
        back_populates="produto"
    )