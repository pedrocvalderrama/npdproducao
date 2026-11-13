"""Peso diário em kg para os lançamentos das SOS."""
from alembic import op
import sqlalchemy as sa

revision = 'f7a9b1c3d526'
down_revision = 'e6f8a0b2c415'
branch_labels = None
depends_on = None


def upgrade():
    existentes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('lancamento_diario')}
    if 'peso_diario' not in existentes:
        op.add_column('lancamento_diario', sa.Column('peso_diario', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('lancamento_diario') as batch:
        batch.drop_column('peso_diario')
