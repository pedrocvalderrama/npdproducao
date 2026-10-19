"""
Autenticação da API JSON somente leitura (Fase 4 da auditoria de otimização).

A API (`/api/v1/...`) foi criada para permitir integrações futuras (ex.: um
BI, uma automação, ou outro sistema da fábrica lendo dados de produção) sem
depender do login por cookie de sessão usado pelas telas HTML. Para isso, ela
aceita uma API key fixa enviada no header `X-API-Key`.

A chave é gerada e persistida em `.api_key` na raiz do projeto (fora do
versionamento, mesmo esquema já usado para `.secret_key`), ou pode ser fixada
via variável de ambiente `API_KEY` (recomendado em produção). Um
administrador pode visualizar e regenerar a chave em `/admin/api-key`.
"""
import os
import secrets

_API_KEY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.api_key')


def _ler_arquivo_chave():
    try:
        if os.path.isfile(_API_KEY_PATH):
            with open(_API_KEY_PATH, 'r', encoding='utf-8') as f:
                chave = f.read().strip()
                if chave:
                    return chave
    except OSError:
        pass
    return None


def _gravar_arquivo_chave(chave):
    try:
        with open(_API_KEY_PATH, 'w', encoding='utf-8') as f:
            f.write(chave)
    except OSError:
        pass


def obter_api_key():
    """Retorna a API key ativa: variável de ambiente API_KEY tem prioridade
    sobre o arquivo `.api_key`; se nenhuma existir, gera e persiste uma nova."""
    env_key = os.environ.get('API_KEY')
    if env_key:
        return env_key
    chave = _ler_arquivo_chave()
    if chave:
        return chave
    chave = secrets.token_urlsafe(32)
    _gravar_arquivo_chave(chave)
    return chave


def regenerar_api_key():
    """Gera uma nova chave e a persiste em `.api_key` (só tem efeito se a
    chave não estiver fixada via variável de ambiente API_KEY)."""
    chave = secrets.token_urlsafe(32)
    _gravar_arquivo_chave(chave)
    return chave


def api_key_valida(header_recebido):
    if not header_recebido:
        return False
    return secrets.compare_digest(header_recebido, obter_api_key())
