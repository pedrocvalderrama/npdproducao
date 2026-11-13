"""Milheiro das produções SOS, preservando pesos anteriores."""
from alembic import op
import sqlalchemy as sa

revision = 'b9c1d3e5f748'
down_revision = 'a8b0c2d4e637'
branch_labels = None
depends_on = None


def upgrade():
    colunas = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('lancamento_diario_producoes')}
    if 'milheiro' not in colunas:
        op.add_column('lancamento_diario_producoes', sa.Column('milheiro', sa.Float(), nullable=True))
    op.execute("""UPDATE lancamento_diario_producoes
        SET milheiro = peso_diario * 1000.0 / quantidade
        WHERE milheiro IS NULL AND quantidade > 0 AND peso_diario IS NOT NULL
          AND lancamento_id IN (SELECT id FROM lancamento_diario
              WHERE equipamento IN ('SOS 1', 'SOS 2', 'SOS 3', 'SOS 4'))""")


def downgrade():
    with op.batch_alter_table('lancamento_diario_producoes') as batch:
        batch.drop_column('milheiro')
