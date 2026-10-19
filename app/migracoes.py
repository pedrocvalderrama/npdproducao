"""
Aplica automaticamente, ao iniciar o servidor, as migrações do Alembic que
ainda não rodaram no banco (ex.: projeto atualizado copiado para o servidor,
mantendo o `dados_producao.db` de lá).

Fluxo:
1. Banco sem controle de versão (nunca passou pelo Alembic): é marcado na
   revisão baseline, sem executar nada — `inicializar_banco()` já deixou o
   schema legado pronto antes desta etapa.
2. Havendo revisões pendentes: faz backup do banco em backup/ e aplica todas.
3. Qualquer falha é registrada em app.log e o servidor sobe mesmo assim
   (as telas antigas continuam funcionando).
"""
import logging
import os
import sqlite3
from datetime import datetime

from .config import DB_NAME

_logger = logging.getLogger('npd.migracoes')

RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVISAO_BASELINE = 'fe480f523c17'
BACKUP_DIR = os.path.join(os.path.dirname(DB_NAME), 'backup')


def _config_alembic():
    # Sem passar o alembic.ini de propósito: com o arquivo, o env.py chama
    # logging.fileConfig e desliga os loggers da aplicação (app.log).
    from alembic.config import Config
    cfg = Config()
    cfg.set_main_option('script_location', os.path.join(RAIZ_PROJETO, 'migrations'))
    return cfg


def _revisao_atual():
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    engine = create_engine(f'sqlite:///{DB_NAME}')
    try:
        with engine.connect() as conexao:
            return MigrationContext.configure(conexao).get_current_revision()
    finally:
        engine.dispose()


def _backup_antes_da_migracao():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    destino = os.path.join(
        BACKUP_DIR,
        f"dados_producao_antes_migracao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
    )
    origem = sqlite3.connect(DB_NAME)
    copia = sqlite3.connect(destino)
    try:
        with copia:
            origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    return destino


def aplicar_migracoes_pendentes():
    """Retorna 'atualizado', 'migrado' ou 'erro' (o detalhe fica no log)."""
    try:
        from alembic import command
        from alembic.script import ScriptDirectory
    except ImportError:
        _logger.error(
            'Alembic não está instalado: migrações do banco NÃO foram aplicadas. '
            'Rode "venv\\Scripts\\python.exe -m pip install -r requirements.txt" e reinicie o servidor.'
        )
        return 'erro'

    try:
        cfg = _config_alembic()
        revisao_final = ScriptDirectory.from_config(cfg).get_current_head()
        revisao = _revisao_atual()

        if revisao is None:
            command.stamp(cfg, REVISAO_BASELINE)
            revisao = REVISAO_BASELINE
            _logger.info('Banco sem controle de versão: marcado na revisão baseline %s.', REVISAO_BASELINE)

        if revisao == revisao_final:
            _logger.info('Banco de dados já está na versão mais recente (%s).', revisao)
            return 'atualizado'

        backup = _backup_antes_da_migracao()
        _logger.info('Backup antes da migração: %s', backup)
        command.upgrade(cfg, 'head')
        _logger.info('Migrações aplicadas: banco atualizado de %s para %s.', revisao, _revisao_atual())
        return 'migrado'
    except Exception:
        _logger.exception('Falha ao aplicar migrações do banco. O servidor vai subir sem elas.')
        return 'erro'
