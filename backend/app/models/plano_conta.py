from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class PlanoConta(Base):
    """Categorizacao contabil hierarquica (ex.: Despesas > Operacionais >
    Aluguel) -- mais estruturada que ContaPagar.categoria (free text).
    So' a relationship com o PAI (pra expor conta_pai_nome sem query
    extra) -- os filhos de um no' sao buscados via
    PlanoContaRepository.listar_filhos, nao por uma collection ORM."""

    __tablename__ = "planos_conta"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    codigo: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    nome: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # RECEITA ou DESPESA -- toda subconta herda o tipo da conta pai
    # (ver PlanoContaService), entao a arvore inteira fica consistente
    # sem precisar recalcular nada em cascata.
    tipo: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    conta_pai_id: Mapped[int | None] = mapped_column(
        ForeignKey("planos_conta.id"),
        index=True,
        nullable=True,
    )

    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    pai = relationship("PlanoConta", remote_side=[id])

    @property
    def conta_pai_nome(self) -> str | None:
        return self.pai.nome if self.pai else None
