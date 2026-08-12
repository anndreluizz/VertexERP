from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Configuracao(Base):
    """Linha única (id=1) com os dados da loja — nome, PIX e logo."""

    __tablename__ = "configuracoes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    nome_loja: Mapped[str] = mapped_column(String(150), nullable=True)
    cnpj_cpf: Mapped[str] = mapped_column(String(20), nullable=True)
    endereco: Mapped[str] = mapped_column(String(255), nullable=True)
    telefone: Mapped[str] = mapped_column(String(20), nullable=True)

    pix_chave: Mapped[str] = mapped_column(String(150), nullable=True)
    pix_nome: Mapped[str] = mapped_column(String(150), nullable=True)
    pix_cidade: Mapped[str] = mapped_column(String(100), nullable=True)

    logo_filename: Mapped[str] = mapped_column(String(255), nullable=True)

    # "sempre", "nunca" ou "perguntar" (padrão) — controla se o PDV
    # pergunta a cada venda se deve imprimir o comprovante.
    impressao_comprovante: Mapped[str] = mapped_column(
        String(20), nullable=True
    )
