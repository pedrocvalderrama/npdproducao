"""Meta percentual de refugo compartilhada pelo quadro semanal SOS."""
from alembic import op
import sqlalchemy as sa

revision = 'c0d2e4f6a859'
down_revision = 'b9c1d3e5f748'
branch_labels = None
depends_on = None


def upgrade():
    if 'configuracao_quadro_sos' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'configuracao_quadro_sos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('meta_refugo_pct', sa.Float(), nullable=True),
        sa.CheckConstraint('id = 1', name='ck_quadro_sos_unico'),
        sa.CheckConstraint('meta_refugo_pct >= 0 AND meta_refugo_pct <= 100',
                           name='ck_quadro_sos_meta_refugo'),
    )
    op.execute('INSERT INTO configuracao_quadro_sos (id, meta_refugo_pct) VALUES (1, NULL)')


def downgrade():
    op.drop_table('configuracao_quadro_sos')
