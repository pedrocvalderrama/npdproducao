"""
Pacote de rotas da aplicação, dividido por área funcional (Fase 3 da
auditoria de otimização). Todas as sub-rotas continuam registradas no
mesmo blueprint "main" (endpoints como `main.historico` não mudam), então
nenhum template ou link precisou ser alterado — a divisão é só de
organização de arquivos, sem mudança de comportamento.
"""
from flask import Blueprint

main_bp = Blueprint('main', __name__)

# Importados por efeito colateral: cada módulo registra suas rotas em
# main_bp ao ser importado. A ordem não importa para o funcionamento,
# mas é mantida igual à ordem original em routes.py.
from . import producao  # noqa: E402,F401
from . import historico  # noqa: E402,F401
from . import pedidos_movimento  # noqa: E402,F401
from . import listagens  # noqa: E402,F401
from . import analise  # noqa: E402,F401
from . import lancamento_diario  # noqa: E402,F401
