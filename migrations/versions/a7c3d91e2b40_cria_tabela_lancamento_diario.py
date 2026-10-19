"""cria tabela lancamento_diario

Revision ID: a7c3d91e2b40
Revises: fe480f523c17
Create Date: 2026-09-29 17:50:00.000000

Tabela isolada da aba "Lançamento Diário" (Produção): uma linha por
equipamento (SOS 1-4, ROBO, RESMADEIRA, GUILHOTINA) e data. Não tem vínculo
com `producao` e não entra em nenhum cálculo existente.
No ROBO, `quantidade` guarda as sacolas e `quantidade_alcas` as alças;
nos demais equipamentos `quantidade_alcas` fica NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3d91e2b40'
down_revision: Union[str, Sequence[str], None] = 'fe480f523c17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lancamento_diario',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('data', sa.Text(), nullable=False),
        sa.Column('equipamento', sa.Text(), nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('quantidade_alcas', sa.Integer(), nullable=True),
        sa.Column('problemas', sa.Text(), nullable=True),
        sa.Column('solucoes', sa.Text(), nullable=True),
        sa.Column('observacao', sa.Text(), nullable=True),
        sa.Column('usuario', sa.Text(), nullable=True),
        sa.Column('criado_em', sa.Text(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index(
        'idx_lancamento_diario_data_equip',
        'lancamento_diario',
        ['data', 'equipamento'],
    )


def downgrade() -> None:
    op.drop_index('idx_lancamento_diario_data_equip', table_name='lancamento_diario')
    op.drop_table('lancamento_diario')
