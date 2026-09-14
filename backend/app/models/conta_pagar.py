from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    LargeBinary,
    Numeric,
    String,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import Base


class ContaPagar(Base):

    __tablename__ = "contas_pagar"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    fornecedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("fornecedores.id"),
        index=True,
        nullable=True,
    )

    compra_id: Mapped[int | None] = mapped_column(
        ForeignKey("compras.id"),
        index=True,
        nullable=True,
    )

    # nullable pelo mesmo motivo das outras entidades com loja_id novo
    # -- contas antigas nao tem essa informacao (backfill na migracao)
    loja_id: Mapped[int | None] = mapped_column(
        ForeignKey("lojas.id"),
        index=True,
        nullable=True,
    )

    data_emissao: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    data_vencimento: Mapped[datetime]

    data_pagamento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    descricao: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    categoria: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    observacao: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    numero_boleto: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDENTE",
    )

    numero_boleto: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    # o boleto/nota em si (PDF ou foto), pra nao depender de papel --
    # mesmo padrao do Cliente.foto (bytes direto no banco, sem depender
    # de disco/storage externo).
    documento: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )

    documento_nome: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    documento_tipo: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    @property
    def tem_documento(self) -> bool:
        return self.documento is not None

    # comprovante de que o pagamento foi feito (print de PIX,
    # transferencia etc.) -- diferente do 'documento' acima, que e o
    # boleto/nota ORIGINAL anexado na criacao da despesa.
    comprovante_pagamento: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )

    comprovante_pagamento_nome: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    comprovante_pagamento_tipo: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    @property
    def tem_comprovante_pagamento(self) -> bool:
        return self.comprovante_pagamento is not None

    # como o pagamento foi feito -- mesmos valores de texto usados em
    # Venda.forma_pagamento (PIX/TRANSFERENCIA/DINHEIRO/CARTAO/BOLETO),
    # so preenchido no momento de marcar a despesa como paga.
    forma_pagamento: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    banco_pagamento: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    numero_transacao: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    fornecedor = relationship(
        "Fornecedor"
    )