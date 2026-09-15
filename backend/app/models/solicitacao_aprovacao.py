from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SolicitacaoAprovacao(Base):
    """Uma acao sensivel pedida por um operador (nao-admin) que fica
    parada aqui ate um administrador aprovar ou rejeitar — pensada
    pra ser aprovada pelo celular, sem precisar o gerente estar no
    caixa. O 'tipo' decide qual acao de verdade roda quando aprovada
    (ver AprovacaoService._executar)."""

    __tablename__ = "solicitacoes_aprovacao"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # EXCLUIR_CLIENTE, e outros tipos que forem entrando com o tempo
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)

    referencia_id: Mapped[int] = mapped_column(nullable=False)

    descricao: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20),
        index=True,
        default="PENDENTE",
    )

    solicitante_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=False,
    )

    aprovador_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=True,
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    resolvido_em: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
