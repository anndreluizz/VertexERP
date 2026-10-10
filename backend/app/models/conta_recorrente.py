from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ContaRecorrente(Base):
    """Conta fixa que se repete todo mês (luz, funcionária, aluguel) --
    o sistema cria sozinho a ContaPagar de cada mês (ver
    ContaRecorrenteService.gerar_pendentes). valor_variavel=True (luz):
    a conta do mês nasce com o valor da anterior e marcada pra
    confirmar; False (funcionária): nasce com o valor fixo daqui."""

    __tablename__ = "contas_recorrentes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    descricao: Mapped[str] = mapped_column(String(120))

    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    # dia do vencimento (1-31); em mês mais curto vence no último dia
    dia_vencimento: Mapped[int] = mapped_column(Integer)

    valor_variavel: Mapped[bool] = mapped_column(Boolean, default=False)

    categoria: Mapped[str | None] = mapped_column(String(60), nullable=True)

    centro_custo: Mapped[str | None] = mapped_column(String(60), nullable=True)

    plano_conta_id: Mapped[int | None] = mapped_column(
        ForeignKey("planos_conta.id"), nullable=True
    )

    observacao: Mapped[str | None] = mapped_column(String(255), nullable=True)

    loja_id: Mapped[int | None] = mapped_column(
        ForeignKey("lojas.id"), index=True, nullable=True
    )

    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    # primeiro dia do último mês já gerado (None = nenhum ainda)
    ultima_competencia: Mapped[date | None] = mapped_column(Date, nullable=True)

    # empréstimo/financiamento: último mês que deve ser criado (None =
    # repete até alguém parar)
    fim_competencia: Mapped[date | None] = mapped_column(Date, nullable=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
