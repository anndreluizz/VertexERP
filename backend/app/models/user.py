from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.permissoes import PERMISSOES_DISPONIVEIS

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    nome: Mapped[str] = mapped_column(String(100), nullable=False)

    # loja onde o usuario trabalha -- NULL so faz sentido pra admin
    # (enxerga/gerencia todas as lojas); usuario comum sempre tem uma.
    # Nao trava a loja que ele OPERA no PDV/caixa -- isso quem decide e
    # o terminal (ver config local do frontend), nao esse campo.
    loja_id: Mapped[int | None] = mapped_column(
        ForeignKey("lojas.id"),
        index=True,
        nullable=True
    )

    email: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True,
        nullable=False
    )

    senha: Mapped[str] = mapped_column(String(255), nullable=False)

    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    # subconjunto de permissoes pra usuario NAO-admin (ver
    # app/models/perfil.py) -- admin=True ignora isso e sempre passa
    # em qualquer checagem (ver exigir_permissao)
    perfil_id: Mapped[int | None] = mapped_column(
        ForeignKey("perfis.id"),
        index=True,
        nullable=True,
    )

    # Coluna preparada pra 2FA (ainda sem fluxo de verificacao completo
    # no app) -- guarda espaco no schema pra nao precisar de outra
    # migration quando o segundo fator entrar de verdade.
    dois_fatores_ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    perfil = relationship("Perfil")

    @property
    def perfil_nome(self) -> str | None:
        return self.perfil.nome if self.perfil else None

    @property
    def permissoes(self) -> list[str]:
        # admin ve o catalogo inteiro (ele passa em qualquer checagem
        # de qualquer forma, ver exigir_permissao) -- assim o frontend
        # pode decidir o que mostrar so' olhando essa lista, sem
        # precisar saber separadamente se e' admin
        if self.admin:
            return list(PERMISSOES_DISPONIVEIS)

        return list(self.perfil.permissoes) if self.perfil else []