from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Venda(Base):
    __tablename__ = "vendas"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id"),
        index=True,
        nullable=True
    )

    # quem vendeu — nullable pra nao quebrar vendas ja existentes (nunca
    # tiveram esse dado) e pra registros futuros sem usuario disponivel
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=True
    )

    # loja onde a venda foi feita -- nullable pelo mesmo motivo do
    # usuario_id acima (vendas antigas nao tem essa informacao); a
    # migracao faz backfill pra loja Matriz em tudo que ja existe
    loja_id: Mapped[int | None] = mapped_column(
        ForeignKey("lojas.id"),
        index=True,
        nullable=True
    )

    data: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    valor_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0
    )

    desconto: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0
    )

    observacao: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="FINALIZADA"
    )

    # NOVO
    forma_pagamento: Mapped[str] = mapped_column(
        String(20),
        default="AVISTA"
    )

    # pagamento dividido (no maximo 2 formas por venda): a forma
    # principal usa valor_total - valor_forma_2, e essa segunda forma
    # cobre o restante — usado pra casos tipo "parte dinheiro parte
    # pix" ou "entrada + resto no fiado"
    forma_pagamento_2: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    valor_forma_2: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    # NOVO
    data_vencimento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    data_fechamento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    # trilha de auditoria do cancelamento (status="CANCELADA") -- a
    # venda em si NUNCA e apagada (ver VendaService.excluir/cancelar),
    # entao esses campos ficam None pra sempre em vendas nunca
    # canceladas e preenchidos quando alguem cancela uma.
    cancelado_em: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    cancelado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=True
    )

    motivo_cancelamento: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    cliente = relationship(
        "Cliente",
        back_populates="vendas"
    )

    itens = relationship(
        "ItemVenda",
        back_populates="venda",
        cascade="all, delete-orphan"
    )

    usuario = relationship("User", foreign_keys=[usuario_id])

    cancelado_por = relationship("User", foreign_keys=[cancelado_por_id])

    @property
    def cancelado_por_nome(self) -> str | None:
        return self.cancelado_por.nome if self.cancelado_por else None

    @property
    def usuario_nome(self) -> str | None:
        return self.usuario.nome if self.usuario else None

    @property
    def lucro(self) -> Decimal | None:
        """Valor total (ja com desconto aplicado) menos o custo dos
        produtos vendidos -- so pra dar visibilidade de margem no
        detalhe da venda; None se algum item nao tiver produto/custo
        disponivel (produto removido, por exemplo)."""

        try:
            custo_total = sum(
                (item.produto.preco_custo or 0) * item.quantidade
                for item in self.itens
            )
            return self.valor_total - custo_total
        except Exception:
            return None