"""cria tabela metas_lancamento_diario

Revision ID: b3e8f5a1c2d7
Revises: a7c3d91e2b40
Create Date: 2026-09-30 13:20:00.000000

Metas mensais do bloco "Meta do Mês" da tela Display Diário, comparadas
apenas com os dados de `lancamento_diario`. Separada de `metas_mensais`
(Comparativo Mensal) para manter o estudo do Lançamento Diário isolado.
`grupo`: SOS (soma de SOS 1-4), IMPRESSORA ou ROBO (sacolas).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3e8f5a1c2d7'
down_revision: Union[str, Sequence[str], None] = 'a7c3d91e2b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'metas_lancamento_diario',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('ano', sa.Integer(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('grupo', sa.Text(), nullable=False),
        sa.Column('meta_quantidade', sa.Integer(), nullable=False),
        sa.UniqueConstraint('ano', 'mes', 'grupo', name='uq_metas_lancamento_diario_ano_mes_grupo'),
    )


def downgrade() -> None:
    op.drop_table('metas_lancamento_diario')
