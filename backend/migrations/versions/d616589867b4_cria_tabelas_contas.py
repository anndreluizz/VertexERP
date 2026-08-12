"""cria tabelas contas

Revision ID: d616589867b4
Revises: 8ed3ca355d45
Create Date: 2026-07-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "d616589867b4"
down_revision: Union[str, Sequence[str], None] = "8ed3ca355d45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Vazio de propósito: contas_receber (migração 2276322528e7) e
    # contas_pagar (migração fe22824d45f9), ambas anteriores nesta mesma
    # cadeia, já criam essas tabelas. O corpo original desta migração
    # duplicava esse CREATE TABLE e travava qualquer `alembic upgrade
    # head` rodado do zero (banco novo) com "relação já existe" — nunca
    # foi percebido porque o banco de dev já tinha passado por essa
    # revisão antes de o duplicado existir. Não altera bancos que já
    # estão além desta revisão (ela simplesmente não roda de novo).
    pass


def downgrade() -> None:
    pass