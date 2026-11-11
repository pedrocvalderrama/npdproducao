"""Horários de produção do Robô para até quatro dias.

Revision ID: d5e7f9a1b203
Revises: c4d2a6b8e913
"""
from alembic import op
import sqlalchemy as sa

revision = 'd5e7f9a1b203'
down_revision = 'c4d2a6b8e913'
branch_labels = None
depends_on = None

HORARIOS = [
    f'{prefixo}_prod_robo{sufixo}'
    for sufixo in ('', '_2', '_3', '_4')
    for prefixo in ('inicio', 'fim')
]


def upgrade():
    existentes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('producao')}
    for coluna in HORARIOS:
        if coluna not in existentes:
            op.add_column('producao', sa.Column(coluna, sa.Text(), nullable=True))
    if 'tempo_prod_robo' not in existentes:
        op.add_column('producao', sa.Column('tempo_prod_robo', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('producao') as batch:
        batch.drop_column('tempo_prod_robo')
        for coluna in reversed(HORARIOS):
            batch.drop_column(coluna)
