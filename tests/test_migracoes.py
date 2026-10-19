"""Migração automática ao iniciar o servidor (app/migracoes.py)."""
import os
import sqlite3


def _tabelas(db):
    conn = sqlite3.connect(db)
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        conn.close()


def _revisao(db):
    conn = sqlite3.connect(db)
    try:
        return conn.execute('SELECT version_num FROM alembic_version').fetchone()[0]
    finally:
        conn.close()


def test_banco_atualizado_nao_faz_nada(app):
    from app.migracoes import aplicar_migracoes_pendentes
    assert aplicar_migracoes_pendentes() == 'atualizado'


def test_banco_antigo_sem_versao_recebe_tabelas_novas_com_backup(app):
    """Simula o banco do servidor: dados existentes, sem alembic_version e sem as tabelas novas."""
    from app.config import DB_NAME
    from app.migracoes import BACKUP_DIR, aplicar_migracoes_pendentes

    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO producao (num_of, servico) VALUES ('PYTEST-MIG-1', 'DADO ANTIGO')")
    conn.execute('DROP TABLE lancamento_diario')
    conn.execute('DROP TABLE metas_lancamento_diario')
    conn.execute('DROP TABLE alembic_version')
    conn.commit()
    conn.close()
    backups_antes = set(os.listdir(BACKUP_DIR)) if os.path.isdir(BACKUP_DIR) else set()

    try:
        assert aplicar_migracoes_pendentes() == 'migrado'

        tabelas = _tabelas(DB_NAME)
        assert {'lancamento_diario', 'metas_lancamento_diario'} <= tabelas

        from alembic.script import ScriptDirectory
        from app.migracoes import _config_alembic
        assert _revisao(DB_NAME) == ScriptDirectory.from_config(_config_alembic()).get_current_head()

        conn = sqlite3.connect(DB_NAME)
        servico = conn.execute("SELECT servico FROM producao WHERE num_of = 'PYTEST-MIG-1'").fetchone()[0]
        conn.close()
        assert servico == 'DADO ANTIGO'

        novos = set(os.listdir(BACKUP_DIR)) - backups_antes
        assert any(n.startswith('dados_producao_antes_migracao_') for n in novos)

        assert aplicar_migracoes_pendentes() == 'atualizado'
    finally:
        conn = sqlite3.connect(DB_NAME)
        conn.execute("DELETE FROM producao WHERE num_of = 'PYTEST-MIG-1'")
        conn.commit()
        conn.close()
