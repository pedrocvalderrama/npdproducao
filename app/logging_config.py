"""
Logging estruturado da aplicação (Fase 4 da auditoria de otimização).

Objetivo: quando o sistema roda como serviço do Windows (via NSSM, sem
janela de console visível), precisamos de arquivos de log persistentes para
diagnosticar problemas depois do fato — erro 500, quem acessou o quê e
quando, se o servidor caiu e por quê. Antes disso a única saída era o
console do `flask run`/`waitress-serve`, que se perde quando roda como
serviço.

Decisão de projeto: usar só `logging` da stdlib (RotatingFileHandler), sem
adicionar dependência nova (ex.: structlog) — o volume de log deste sistema
não justifica a complexidade extra, e "estruturado" aqui significa um
formato de linha único e consistente (fácil de grep/filtrar), não JSON.
"""
import logging
import os
import time
from logging.handlers import RotatingFileHandler

from flask import g, request

from .config import LOG_DIR, LOG_LEVEL

MAX_BYTES = 5 * 1024 * 1024  # 5 MB por arquivo
BACKUP_COUNT = 5  # mantém os últimos 5 arquivos rotacionados (~25 MB no total)

_FORMATO = '%(asctime)s %(levelname)s [%(name)s] %(message)s'
_FORMATO_DATA = '%Y-%m-%d %H:%M:%S'


def _criar_handler_arquivo(nome_arquivo, nivel):
    os.makedirs(LOG_DIR, exist_ok=True)
    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, nome_arquivo),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding='utf-8',
    )
    handler.setLevel(nivel)
    handler.setFormatter(logging.Formatter(_FORMATO, datefmt=_FORMATO_DATA))
    return handler


def configurar_logging(app):
    """
    Configura `app.logger` (erros, avisos, mensagens da aplicação) e o
    logging de cada requisição HTTP (uma linha por requisição, nível INFO,
    em arquivo separado — parecido com um access log de servidor web).

    Chamado uma vez em `create_app()`. Idempotente: se os handlers já foram
    adicionados (ex.: chamado duas vezes em testes), não duplica.
    """
    nivel = getattr(logging, LOG_LEVEL, logging.INFO)

    # Handler fica no logger raiz (não só em app.logger), para que qualquer
    # módulo (ex.: app/backup.py, com seu próprio `logging.getLogger(...)`)
    # também grave em app.log só por propagação, sem precisar configurar
    # cada logger individualmente.
    raiz = logging.getLogger()
    if not any(isinstance(h, RotatingFileHandler) and h.baseFilename.endswith('app.log') for h in raiz.handlers):
        raiz.addHandler(_criar_handler_arquivo('app.log', nivel))
    raiz.setLevel(nivel)
    app.logger.setLevel(nivel)

    logger_acesso = logging.getLogger('npd.acesso')
    if not any(isinstance(h, RotatingFileHandler) and h.baseFilename.endswith('access.log') for h in logger_acesso.handlers):
        logger_acesso.addHandler(_criar_handler_arquivo('access.log', logging.INFO))
    logger_acesso.setLevel(logging.INFO)
    logger_acesso.propagate = False

    @app.before_request
    def _marcar_inicio_requisicao():
        g._log_inicio = time.monotonic()

    @app.after_request
    def _logar_requisicao(response):
        duracao_ms = (time.monotonic() - g.get('_log_inicio', time.monotonic())) * 1000
        usuario = 'anonimo'
        try:
            from flask_login import current_user
            if current_user and current_user.is_authenticated:
                usuario = current_user.username
        except Exception:
            pass
        logger_acesso.info(
            'metodo=%s rota=%s status=%s duracao_ms=%.1f usuario=%s ip=%s',
            request.method, request.path, response.status_code, duracao_ms,
            usuario, request.headers.get('X-Forwarded-For', request.remote_addr),
        )
        return response

    @app.teardown_request
    def _logar_excecao_nao_tratada(erro):
        if erro is not None:
            app.logger.exception('Excecao nao tratada em %s %s', request.method, request.path, exc_info=erro)

    app.logger.info('Logging configurado (nivel=%s, pasta=%s)', LOG_LEVEL, LOG_DIR)
