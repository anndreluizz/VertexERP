from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Perfil(Base):
    """Conjunto nomeado de permissoes (ver app/auth/permissoes.py pro
    catalogo de chaves validas) -- usuario.admin continua sendo o
    superusuario que ignora qualquer checagem de perfil (ver
    exigir_permissao em app/auth/dependencies.py); perfil e' so' pra
    dar a um usuario COMUM um subconjunto das acoes hoje travadas em
    admin, sem precisar promove-lo a admin de verdade."""

    __tablename__ = "perfis"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    nome: Mapped[str] = mapped_column(
        String(60),
        unique=True,
        nullable=False,
    )

    permissoes: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
    )
