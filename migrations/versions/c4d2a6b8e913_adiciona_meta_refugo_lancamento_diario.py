"""adiciona meta_diaria e refugo_diario em lancamento_diario

Revision ID: c4d2a6b8e913
Revises: b3e8f5a1c2d7
Create Date: 2026-10-06 16:40:00.000000

Campos "Meta Diária" e "Refugo Diário" informados por equipamento na tela
Lançamento Diário. NULL quando não informados.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d2a6b8e913'
down_revision: Union[str, Sequence[str], None] = 'b3e8f5a1c2d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('lancamento_diario') as batch_op:
        batch_op.add_column(sa.Column('meta_diaria', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('refugo_diario', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('lancamento_diario') as batch_op:
        batch_op.drop_column('refugo_diario')
        batch_op.drop_column('meta_diaria')
