"""Divide o refugo diário SOS em Impressora e SOS, preservando totais antigos."""
from alembic import op
import sqlalchemy as sa

revision = 'e6f8a0b2c415'
down_revision = 'd5e7f9a1b203'
branch_labels = None
depends_on = None


def upgrade():
    existentes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('lancamento_diario')}
    for nome in ('refugo_impressora', 'refugo_sos'):
        if nome not in existentes:
            op.add_column('lancamento_diario', sa.Column(nome, sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('lancamento_diario') as batch:
        batch.drop_column('refugo_impressora')
        batch.drop_column('refugo_sos')
