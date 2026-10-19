"""
Configuração da suíte de testes: cria um banco SQLite temporário e isolado
para cada sessão de testes, garantindo que nenhum teste toque no
`dados_producao.db` real usado na fábrica.

IMPORTANTE: as variáveis de ambiente precisam ser definidas ANTES de
importar qualquer módulo de `app`, pois `app/config.py` lê `DB_NAME` uma
única vez, no momento da importação.
"""
import os
import shutil
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix='npd_test_')
os.environ['DB_NAME'] = os.path.join(_TMP_DIR, 'test_dados_producao.db')
os.environ['ADMIN_PASSWORD'] = 'admin123'
os.environ['SECRET_KEY'] = 'chave-de-teste-nao-usar-em-producao'
# Fixa a API key nos testes (evita gerar/gravar `.api_key` de verdade na raiz
# do projeto a cada execução da suíte).
os.environ['API_KEY'] = 'chave-de-teste-da-api'

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.models import inicializar_banco  # noqa: E402
from database.connection import criar_tabelas_custo  # noqa: E402


@pytest.fixture(scope='session', autouse=True)
def _cleanup_tmp_dir():
    yield
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture(scope='session')
def app():
    from app.migracoes import aplicar_migracoes_pendentes

    inicializar_banco()
    criar_tabelas_custo()
    assert aplicar_migracoes_pendentes() in ('atualizado', 'migrado')
    flask_app = create_app()
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin_client(app):
    c = app.test_client()
    c.post('/login', data={'username': 'admin', 'senha': 'admin123'}, follow_redirects=True)
    return c


@pytest.fixture()
def gerente_client(app):
    from app.auth import criar_usuario
    criar_usuario('teste_gerente', 'Teste Gerente', 'senha123', 'gerente')
    c = app.test_client()
    c.post('/login', data={'username': 'teste_gerente', 'senha': 'senha123'}, follow_redirects=True)
    return c


@pytest.fixture()
def inicial_client(app):
    from app.auth import criar_usuario
    criar_usuario('teste_inicial', 'Teste Inicial', 'senha123', 'inicial')
    c = app.test_client()
    c.post('/login', data={'username': 'teste_inicial', 'senha': 'senha123'}, follow_redirects=True)
    return c
