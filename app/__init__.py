# Configura a localidade para datas em português do Brasil
import locale
import os
import secrets
from flask import Flask, flash, jsonify, redirect, request, url_for
from flask_login import current_user
from flask_wtf import CSRFProtect

locale.setlocale(locale.LC_TIME, 'pt_BR.utf8' if locale.getpreferredencoding() != 'cp1252' else 'Portuguese_Brazil.1252')

csrf = CSRFProtect()

# Endpoints acessíveis sem login (tela de login e arquivos estáticos)
ENDPOINTS_PUBLICOS = {'auth.login', 'static'}

_SECRET_KEY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.secret_key')


def _obter_ou_criar_secret_key():
    try:
        if os.path.isfile(_SECRET_KEY_PATH):
            with open(_SECRET_KEY_PATH, 'r', encoding='utf-8') as f:
                chave = f.read().strip()
                if chave:
                    return chave
        chave = secrets.token_hex(32)
        with open(_SECRET_KEY_PATH, 'w', encoding='utf-8') as f:
            f.write(chave)
        return chave
    except OSError:
        # Sem permissão de escrita: cai de volta para uma chave por execução
        return secrets.token_hex(32)

# Função factory para criar a aplicação Flask
def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    # Chave secreta para sessões e segurança: via variável de ambiente em produção.
    # Sem SECRET_KEY definida, usa/gera uma chave persistida em .secret_key na raiz
    # do projeto (arquivo local, fora do versionamento) — evita deslogar todos os
    # operadores a cada reinício do servidor, já que o login agora é obrigatório.
    app.secret_key = os.environ.get('SECRET_KEY') or _obter_ou_criar_secret_key()
    # Protege todos os POST/PUT/PATCH/DELETE contra CSRF (formulários precisam
    # do campo csrf_token; chamadas AJAX usam o header X-CSRFToken)
    csrf.init_app(app)

    # Logging em arquivo (app.log + access.log em LOG_DIR), essencial quando
    # o servidor roda como serviço do Windows sem console visível (Fase 4).
    from .logging_config import configurar_logging
    configurar_logging(app)

    # Autenticação por operador (login obrigatório em todas as rotas, exceto /login)
    from .auth import auth_bp, init_login_manager, inicializar_tabela_usuarios, login_manager
    inicializar_tabela_usuarios()
    init_login_manager(app)
    app.register_blueprint(auth_bp)

    @app.before_request
    def exigir_login():
        if request.endpoint is None or request.endpoint in ENDPOINTS_PUBLICOS:
            return None
        # Rotas da API JSON (/api/v1/...) aceitam autenticação por header
        # X-API-Key, além da sessão de login normal — pensadas para serem
        # chamadas por outros sistemas, não só pelo navegador.
        if request.endpoint.startswith('api.'):
            from .api_auth import api_key_valida
            if api_key_valida(request.headers.get('X-API-Key')) or current_user.is_authenticated:
                return None
            return jsonify({'erro': 'Não autenticado. Envie o header X-API-Key ou faça login.'}), 401
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_user.pode_acessar_endpoint(request.endpoint):
            flash('Você não tem permissão para acessar esta página.', 'danger')
            return redirect(url_for('main.index'))

    @app.errorhandler(403)
    def acesso_negado(_erro):
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('main.index'))

    # Importa e registra o blueprint principal (produção)
    from .routes import main_bp
    app.register_blueprint(main_bp)

    # API JSON somente leitura, para integrações futuras (Fase 4 da auditoria)
    from .routes.api import api_bp
    app.register_blueprint(api_bp)
    csrf.exempt(api_bp)

    # Importa e registra os blueprints de custo
    from .custo.routes.custos_papel import bp as custos_papel_bp
    from .custo.routes.custos_operacionais import bp as custos_operacionais_bp
    from .custo.routes.relatorio import bp as relatorio_bp
    app.register_blueprint(custos_papel_bp)
    app.register_blueprint(custos_operacionais_bp)
    app.register_blueprint(relatorio_bp)

    from .routes.formatos import bp as formatos_bp
    app.register_blueprint(formatos_bp)

    from .config import ALL_MAQUINAS, MAQUINAS_SOS

    @app.context_processor
    def inject_config():
        return {'all_maquinas': ALL_MAQUINAS, 'maquinas_sos': MAQUINAS_SOS}

    # Retorna a aplicação pronta para uso
    return app
