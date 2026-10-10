from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class BeneficiarioBoleto(Base):
    """Memória de "quem é" o beneficiário de um boleto: o código de
    barras não traz o nome do fornecedor, mas traz a agência/conta (ou
    código) de quem recebe -- ver boleto_service.chave_beneficiario. Na
    primeira vez a pessoa digita "ADRIANA"; nas próximas o nome e a
    categoria já vêm preenchidos ao bipar um boleto do mesmo
    beneficiário. Também guarda por CNPJ (lido do PDF)."""

    __tablename__ = "beneficiarios_boleto"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # "237:12340098765", "arrec:3:0048" ou "cnpj:12345678000199"
    chave: Mapped[str] = mapped_column(String(40), unique=True, index=True)

    nome: Mapped[str] = mapped_column(String(120))

    categoria: Mapped[str | None] = mapped_column(String(60), nullable=True)

    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
