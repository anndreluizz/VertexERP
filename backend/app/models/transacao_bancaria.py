from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class TransacaoBancaria(Base):
    """Uma linha do extrato bancario importado (arquivo OFX) -- ver
    ExtratoBancarioService. fitid e' o identificador unico que o banco
    da pra cada transacao (mesmo campo usado no OFX), usado pra nao
    reimportar a mesma linha duas vezes se o usuario subir o mesmo
    arquivo (ou um com periodo sobreposto) de novo."""

    __tablename__ = "transacoes_bancarias"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    loja_id: Mapped[int | None] = mapped_column(
        ForeignKey("lojas.id"),
        index=True,
        nullable=True,
    )

    fitid: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )

    data: Mapped[date] = mapped_column(Date, nullable=False)

    descricao: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # positivo = credito (entrada), negativo = debito (saida) -- mesma
    # convencao de sinal do OFX (TRNAMT)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    tipo: Mapped[str] = mapped_column(String(10), nullable=False)

    # PENDENTE -> CONCILIADA (linkada a uma ContaPagar/ContaReceber) ou
    # IGNORADA (nao corresponde a nada rastreado, ex.: tarifa bancaria,
    # transferencia entre contas proprias)
    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDENTE",
    )

    conta_pagar_id: Mapped[int | None] = mapped_column(
        ForeignKey("contas_pagar.id"),
        index=True,
        nullable=True,
    )

    conta_receber_id: Mapped[int | None] = mapped_column(
        ForeignKey("contas_receber.id"),
        index=True,
        nullable=True,
    )

    conciliado_em: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    conciliado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
    )

    conta_pagar = relationship("ContaPagar")
    conta_receber = relationship("ContaReceber")
    conciliado_por = relationship("User")

    @property
    def conta_pagar_descricao(self) -> str | None:
        return self.conta_pagar.descricao if self.conta_pagar else None

    @property
    def conta_receber_descricao(self) -> str | None:
        if not self.conta_receber:
            return None
        return self.conta_receber.observacao or f"Venda #{self.conta_receber.venda_id}"

    @property
    def conciliado_por_nome(self) -> str | None:
        return self.conciliado_por.nome if self.conciliado_por else None
