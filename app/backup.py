"""
Backup automático do banco de dados SQLite.

Faz uma cópia consistente (via API de backup do sqlite3, segura mesmo com o
banco em uso) ao iniciar o servidor e depois a cada 24 horas, guardando os
últimos 30 dias em backup/. Não depende de bibliotecas externas nem de
agendador do sistema operacional.
"""
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime

from .config import DB_NAME

BACKUP_DIR = os.path.join(os.path.dirname(DB_NAME), 'backup')
BACKUP_RETENTION_DAYS = 30
BACKUP_INTERVAL_SECONDS = 24 * 60 * 60

# Usa o mesmo logger em arquivo configurado em app/logging_config.py: assim
# o resultado dos backups automáticos fica registrado mesmo quando o
# servidor roda como serviço do Windows, sem console visível (Fase 4).
_logger = logging.getLogger('npd.backup')


def _fazer_backup_agora():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    destino = os.path.join(BACKUP_DIR, f'dados_producao_{timestamp}.db')
    try:
        origem = sqlite3.connect(DB_NAME)
        copia = sqlite3.connect(destino)
        with copia:
            origem.backup(copia)
        copia.close()
        origem.close()
        _logger.info('Backup criado: %s', destino)
    except Exception:
        _logger.exception('Falha ao gerar backup')
        return
    _limpar_backups_antigos()


def _limpar_backups_antigos():
    limite = time.time() - BACKUP_RETENTION_DAYS * 86400
    try:
        for nome in os.listdir(BACKUP_DIR):
            caminho = os.path.join(BACKUP_DIR, nome)
            if nome.startswith('dados_producao_') and nome.endswith('.db') and os.path.isfile(caminho):
                if os.path.getmtime(caminho) < limite:
                    os.remove(caminho)
    except Exception:
        _logger.exception('Falha ao limpar backups antigos')


def _loop_backup():
    while True:
        _fazer_backup_agora()
        time.sleep(BACKUP_INTERVAL_SECONDS)


def iniciar_backup_automatico():
    """Dispara backup imediato e agenda backups diários em thread separada (daemon)."""
    thread = threading.Thread(target=_loop_backup, daemon=True, name='backup-diario')
    thread.start()
