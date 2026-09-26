from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class LogAuditoria(Base):
    """Registro de quem exerceu uma acao sensivel (qualquer coisa
    gatada por exigir_permissao/get_current_admin -- ver
    app/auth/dependencies.py), quando e de que IP. So' cresce, nunca e'
    editado/apagado (mesmo motivo do ContaPagarEvento).

    Escopo deliberado: registra QUE a acao foi autorizada (quem/quando/
    onde/qual chave), nao um diff antes-depois de cada campo mudado --
    isso exigiria instrumentar toda service individualmente, escopo bem
    maior. 'detalhes' carrega um resumo legivel quando a rota manda um
    (ex. "Produto #42 - Arroz 5kg"), mas fica None quando a rota so'
    chama Depends(exigir_permissao(...)) sem repassar contexto."""

    __tablename__ = "logs_auditoria"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=True,
    )

    # chave de permissao (ver app/auth/permissoes.py) ou uma acao
    # admin-only sem chave delegavel (ex.: "usuarios.promover")
    acao: Mapped[str] = mapped_column(String(60), nullable=False, index=True)

    detalhes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    data: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    usuario = relationship("User")

    @property
    def usuario_nome(self) -> str | None:
        return self.usuario.nome if self.usuario else None
