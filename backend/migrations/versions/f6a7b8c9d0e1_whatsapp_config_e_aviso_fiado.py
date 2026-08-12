"""whatsapp: configuracao da loja + controle de aviso de fiado parado

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'configuracoes',
        sa.Column('whatsapp_instance_id', sa.String(length=100), nullable=True),
    )
    op.add_column(
        'configuracoes',
        sa.Column('whatsapp_token', sa.String(length=150), nullable=True),
    )
    op.add_column(
        'configuracoes',
        sa.Column(
            'whatsapp_ativo', sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'configuracoes',
        sa.Column(
            'whatsapp_lembrete_fiado_ativo', sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'configuracoes',
        sa.Column(
            'whatsapp_lembrete_fiado_dias', sa.Integer(), nullable=False,
            server_default='30',
        ),
    )
    op.add_column(
        'configuracoes',
        sa.Column(
            'whatsapp_comprovante_venda_ativo', sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ),
    )

    # marca quando o cliente foi avisado pela ultima vez sobre fiado
    # parado -- evita mandar a mesma mensagem todo santo dia enquanto
    # ele nao pagar (ver whatsapp_lembrete_service.py)
    op.add_column(
        'clientes',
        sa.Column('whatsapp_fiado_avisado_em', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('clientes', 'whatsapp_fiado_avisado_em')

    op.drop_column('configuracoes', 'whatsapp_comprovante_venda_ativo')
    op.drop_column('configuracoes', 'whatsapp_lembrete_fiado_dias')
    op.drop_column('configuracoes', 'whatsapp_lembrete_fiado_ativo')
    op.drop_column('configuracoes', 'whatsapp_ativo')
    op.drop_column('configuracoes', 'whatsapp_token')
    op.drop_column('configuracoes', 'whatsapp_instance_id')
