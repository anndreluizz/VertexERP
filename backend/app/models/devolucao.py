from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Devolucao(Base):
    """Devolução parcial (ou total, item por item) de uma venda já
    finalizada -- a venda continua FINALIZADA, só os itens devolvidos
    voltam pro estoque e o valor sai do caixa (ver DevolucaoService).
    Diferente do cancelamento, que desfaz a venda inteira."""

    __tablename__ = "devolucoes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    venda_id: Mapped[int] = mapped_column(ForeignKey("vendas.id"), index=True)

    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=True
    )

    data: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    # DINHEIRO/PIX/DEBITO/CREDITO = valor devolvido por essa forma;
    # PRAZO = abatido do fiado do cliente
    forma_reembolso: Mapped[str] = mapped_column(String(20))

    motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)

    itens = relationship(
        "ItemDevolucao", back_populates="devolucao", cascade="all, delete-orphan"
    )
    usuario = relationship("User")

    @property
    def usuario_nome(self) -> str | None:
        return self.usuario.nome if self.usuario else None


class ItemDevolucao(Base):

    __tablename__ = "itens_devolucao"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    devolucao_id: Mapped[int] = mapped_column(
        ForeignKey("devolucoes.id"), index=True
    )

    item_venda_id: Mapped[int] = mapped_column(
        ForeignKey("itens_venda.id"), index=True
    )

    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"))

    quantidade: Mapped[Decimal] = mapped_column(Numeric(12, 3))

    # valor já com a parte proporcional do desconto/acréscimo da venda
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    devolucao = relationship("Devolucao", back_populates="itens")
    produto = relationship("Produto")

    @property
    def produto_nome(self) -> str | None:
        return self.produto.nome if self.produto else None
