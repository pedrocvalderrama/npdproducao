"""Detalhamento de até dez produções por lançamento diário."""
from alembic import op
import sqlalchemy as sa

revision = 'a8b0c2d4e637'
down_revision = 'f7a9b1c3d526'
branch_labels = None
depends_on = None


def upgrade():
    if 'lancamento_diario_producoes' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'lancamento_diario_producoes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lancamento_id', sa.Integer(), sa.ForeignKey('lancamento_diario.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ordem', sa.Integer(), nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False),
        sa.Column('quantidade_alcas', sa.Integer(), nullable=True),
        sa.Column('peso_diario', sa.Float(), nullable=True),
        sa.Column('refugo_diario', sa.Float(), nullable=True),
        sa.Column('refugo_impressora', sa.Float(), nullable=True),
        sa.Column('refugo_sos', sa.Float(), nullable=True),
        sa.CheckConstraint('ordem BETWEEN 1 AND 10', name='ck_producoes_ordem'),
        sa.UniqueConstraint('lancamento_id', 'ordem', name='uq_producoes_lancamento_ordem'),
    )


def downgrade():
    op.drop_table('lancamento_diario_producoes')
