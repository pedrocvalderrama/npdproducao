"""baseline schema atual

Revision ID: fe480f523c17
Revises:
Create Date: 2026-08-01 14:22:30.067914

Marca o ponto de partida do controle de versão do schema com Alembic
(Fase 3 da auditoria de otimização). Antes desta revisão, o schema evoluía
via ~40 `ALTER TABLE ... ADD COLUMN` dentro de `inicializar_banco()`
(app/models.py), cada um dentro de um try/except para ser idempotente.

Essa função continua sendo a fonte da verdade do schema "legado" e é
reaproveitada aqui (em vez de duplicar 40 instruções) para que:
- Um banco novo (`alembic upgrade head` numa instalação limpa) fique com o
  schema completo, idêntico ao de hoje.
- Um banco de produção já existente seja apenas "carimbado" nesta revisão
  (`alembic stamp head`), sem reexecutar nada, já que o schema já está
  nesse estado.

Toda mudança de schema **a partir de agora** deve ser uma nova revisão do
Alembic (`alembic revision -m "..."`) com `upgrade()`/`downgrade()`
explícitos, em vez de outro ALTER TABLE ad-hoc em models.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe480f523c17'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria o schema completo (tabelas producao/pedidos/metas_mensais/usuarios/
    custo_papel/custo_operacional + índices), reaproveitando as funções de
    inicialização já existentes e testadas — evita reescrever manualmente
    (com risco de erro) os ~40 ALTER TABLE que already existem em models.py."""
    from app.auth import inicializar_tabela_usuarios
    from app.models import inicializar_banco
    from database.connection import criar_tabelas_custo

    inicializar_banco()
    criar_tabelas_custo()
    inicializar_tabela_usuarios()


def downgrade() -> None:
    """Não há downgrade automático: este é o schema mínimo funcional da
    aplicação. Reverter significaria apagar tabelas com dados de produção
    reais, o que deve ser uma decisão manual e explícita, não automatizada."""
    raise NotImplementedError(
        "Downgrade da revisão baseline não é suportado (apagaria dados de produção)."
    )
