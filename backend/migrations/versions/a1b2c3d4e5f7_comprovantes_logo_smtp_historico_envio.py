"""comprovantes: logo/smtp da loja + historico de envio

Revision ID: a1b2c3d4e5f7
Revises: f6a7b8c9d0e1
Create Date: 2026-08-06 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # logo da loja pro cabecalho do comprovante -- mesmo padrao de
    # Cliente.foto (bytes direto no banco, sem depender de caminho de
    # arquivo local que nao existe mais depois de trocar de PC).
    op.add_column(
        'configuracoes',
        sa.Column('logo', sa.LargeBinary(), nullable=True),
    )

    # SMTP pra "Enviar por E-mail" -- credencial de terceiro (Gmail,
    # etc.), nunca hardcoded, sempre configurada pela loja.
    op.add_column(
        'configuracoes',
        sa.Column('smtp_host', sa.String(length=150), nullable=True),
    )
    op.add_column(
        'configuracoes',
        sa.Column('smtp_porta', sa.Integer(), nullable=False, server_default='587'),
    )
    op.add_column(
        'configuracoes',
        sa.Column('smtp_usuario', sa.String(length=150), nullable=True),
    )
    op.add_column(
        'configuracoes',
        sa.Column('smtp_senha', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'configuracoes',
        sa.Column('smtp_remetente', sa.String(length=150), nullable=True),
    )
    op.add_column(
        'configuracoes',
        sa.Column(
            'smtp_ativo', sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ),
    )

    # historico de envio do comprovante -- nunca apagado (ver
    # ComprovanteEnvioService), fica pra auditoria de quem mandou o
    # que pra quem.
    op.create_table(
        'comprovante_envios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('venda_id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('canal', sa.String(length=20), nullable=False),
        sa.Column('destino', sa.String(length=150), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('erro', sa.String(length=255), nullable=True),
        sa.Column('data', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['venda_id'], ['vendas.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(['usuario_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_comprovante_envios_id'),
        'comprovante_envios', ['id'], unique=False,
    )
    op.create_index(
        op.f('ix_comprovante_envios_venda_id'),
        'comprovante_envios', ['venda_id'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_comprovante_envios_venda_id'),
        table_name='comprovante_envios',
    )
    op.drop_index(
        op.f('ix_comprovante_envios_id'), table_name='comprovante_envios',
    )
    op.drop_table('comprovante_envios')

    op.drop_column('configuracoes', 'smtp_ativo')
    op.drop_column('configuracoes', 'smtp_remetente')
    op.drop_column('configuracoes', 'smtp_senha')
    op.drop_column('configuracoes', 'smtp_usuario')
    op.drop_column('configuracoes', 'smtp_porta')
    op.drop_column('configuracoes', 'smtp_host')
    op.drop_column('configuracoes', 'logo')
