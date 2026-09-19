from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class TransferenciaEstoque(Base):
    """Cabecalho de uma transferencia de produto entre duas lojas -- os
    movimentos de estoque de verdade (SAIDA na origem, ENTRADA no
    destino) ficam em MovimentoEstoque, amarrados aqui via
    MovimentoEstoque.transferencia_id. Essa tabela existe so' pra
    agrupar os dois movimentos como uma unica operacao (pra listar/
    exibir/eventualmente estornar como uma coisa so, nao dois
    movimentos soltos sem relacao aparente entre si)."""

    __tablename__ = "transferencias_estoque"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id"),
        index=True,
        nullable=False,
    )

    loja_origem_id: Mapped[int] = mapped_column(
        ForeignKey("lojas.id"),
        index=True,
        nullable=False,
    )

    loja_destino_id: Mapped[int] = mapped_column(
        ForeignKey("lojas.id"),
        index=True,
        nullable=False,
    )

    quantidade: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=False,
    )

    motivo: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    data: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    produto = relationship("Produto")
    loja_origem = relationship("Loja", foreign_keys=[loja_origem_id])
    loja_destino = relationship("Loja", foreign_keys=[loja_destino_id])
    usuario = relationship("User")
