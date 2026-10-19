"""
Autenticação e controle de acesso por papel (Fase 2 da auditoria de otimização).

Cada operador cadastrado em app/config.py (ALL_OPERADORES) ganha uma conta
própria automaticamente na primeira execução, com login = nome normalizado e
senha inicial igual ao login (papel "Inicial" por padrão). Um usuário 'admin'
também é criado automaticamente (papel "Admin").

Além disso, um administrador pode cadastrar contas independentes dos
operadores (ex.: pessoas fora do chão de fábrica) em /admin/usuarios,
escolhendo usuário, senha e papel de acesso livremente.

Papéis de acesso:
- inicial: acessa Produção e Custos, mas não Pedidos/Movimento (nem aparecem
  no menu). O lançamento de custo por pedido (dentro de Custos) continua liberado.
  Em Configurações, só troca a própria senha.
- gerente: acesso completo a todas as páginas + cadastro de formatos em
  Configurações.
- admin: acesso completo + pode cadastrar/gerenciar usuários + formatos.
"""
import os
import re
import secrets
import unicodedata

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

from .config import ALL_OPERADORES
from .models import get_db_connection

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Faça login para acessar o sistema.'
login_manager.login_message_category = 'warning'

auth_bp = Blueprint('auth', __name__)

ROLE_INICIAL = 'inicial'
ROLE_GERENTE = 'gerente'
ROLE_ADMIN = 'admin'
ROLES_VALIDAS = {ROLE_INICIAL, ROLE_GERENTE, ROLE_ADMIN}
ROLE_LABELS = {ROLE_INICIAL: 'Inicial', ROLE_GERENTE: 'Gerente', ROLE_ADMIN: 'Admin'}

# Endpoints do menu Pedidos/Movimento, indisponíveis para o papel "Inicial"
ROTAS_RESTRITAS_INICIAL = {
    'main.pedidos',
    'main.atualizar_pedidos',
    'main.excluir_pedido_route',
    'main.movimento',
    'main.atualizar_movimento',
}


def normalizar_username(nome):
    sem_acento = unicodedata.normalize('NFKD', nome or '').encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-z0-9]+', '.', sem_acento.lower()).strip('.')
    return slug or 'usuario'


class Usuario(UserMixin):
    def __init__(self, row):
        self.id = row['id']
        self.username = row['username']
        self.nome = row['nome']
        self.role = row['role'] if row['role'] in ROLES_VALIDAS else ROLE_INICIAL
        self.ativo = bool(row['ativo'])

    def get_id(self):
        return str(self.id)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def pode_gerenciar_formatos(self):
        return self.role in (ROLE_GERENTE, ROLE_ADMIN)

    @property
    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)

    def pode_acessar_endpoint(self, endpoint):
        if self.role == ROLE_INICIAL and endpoint in ROTAS_RESTRITAS_INICIAL:
            return False
        return True


def inicializar_tabela_usuarios():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # Migração: adiciona a coluna `role`, preenchendo com base em is_admin
    # para contas já existentes.
    colunas = {row['name'] for row in conn.execute("PRAGMA table_info(usuarios)").fetchall()}
    if 'role' not in colunas:
        conn.execute(f"ALTER TABLE usuarios ADD COLUMN role TEXT NOT NULL DEFAULT '{ROLE_INICIAL}'")
        conn.execute(f"UPDATE usuarios SET role = '{ROLE_ADMIN}' WHERE is_admin = 1")
        conn.commit()

    existentes = {row['username'] for row in conn.execute("SELECT username FROM usuarios").fetchall()}

    criados = []
    for nome in ALL_OPERADORES:
        username = normalizar_username(nome)
        if username not in existentes:
            conn.execute(
                "INSERT INTO usuarios (username, nome, senha_hash, is_admin, role) VALUES (?, ?, ?, 0, ?)",
                (username, nome, generate_password_hash(username), ROLE_INICIAL),
            )
            existentes.add(username)
            criados.append(username)

    if 'admin' not in existentes:
        admin_password = os.environ.get('ADMIN_PASSWORD') or secrets.token_urlsafe(9)
        conn.execute(
            "INSERT INTO usuarios (username, nome, senha_hash, is_admin, role) VALUES (?, ?, ?, 1, ?)",
            ('admin', 'Administrador', generate_password_hash(admin_password), ROLE_ADMIN),
        )
        if not os.environ.get('ADMIN_PASSWORD'):
            print(f"[auth] Usuário 'admin' criado. Senha inicial: {admin_password} (defina a variável de ambiente ADMIN_PASSWORD para fixar uma senha)")

    conn.commit()
    conn.close()

    if criados:
        print(f"[auth] Usuários criados a partir de app/config.py (senha inicial = mesmo login, trocar em /trocar-senha): {', '.join(criados)}")


def _buscar_usuario_por_id(user_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return Usuario(row) if row else None


def _buscar_row_por_username(username):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM usuarios WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row


def listar_usuarios():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM usuarios ORDER BY nome COLLATE NOCASE").fetchall()
    conn.close()
    return rows


def criar_usuario(username, nome, senha, role):
    username = normalizar_username(username)
    conn = get_db_connection()
    try:
        existe = conn.execute("SELECT 1 FROM usuarios WHERE username = ?", (username,)).fetchone()
        if existe:
            return False, f"Já existe um usuário com o login '{username}'."
        conn.execute(
            "INSERT INTO usuarios (username, nome, senha_hash, is_admin, role) VALUES (?, ?, ?, ?, ?)",
            (username, nome, generate_password_hash(senha), 1 if role == ROLE_ADMIN else 0, role),
        )
        conn.commit()
        return True, f"Usuário '{username}' criado com sucesso."
    finally:
        conn.close()


def definir_senha(user_id, nova_senha):
    conn = get_db_connection()
    conn.execute(
        "UPDATE usuarios SET senha_hash = ? WHERE id = ?",
        (generate_password_hash(nova_senha), user_id),
    )
    conn.commit()
    conn.close()


def alternar_ativo(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE usuarios SET ativo = 1 - ativo WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def init_login_manager(app):
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return _buscar_usuario_por_id(user_id)


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """Exige que o usuário autenticado tenha um dos papéis informados."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapper
    return decorator


def _processar_troca_senha():
    """Valida e aplica troca da própria senha. Retorna True se salvou."""
    senha_atual = request.form.get('senha_atual', '')
    nova_senha = request.form.get('nova_senha', '')
    confirmar_senha = request.form.get('confirmar_senha', '')
    row = _buscar_row_por_username(current_user.username)
    if not row or not check_password_hash(row['senha_hash'], senha_atual):
        flash('Senha atual incorreta.', 'danger')
        return False
    if len(nova_senha) < 4:
        flash('A nova senha deve ter pelo menos 4 caracteres.', 'danger')
        return False
    if nova_senha != confirmar_senha:
        flash('A confirmação não confere com a nova senha.', 'danger')
        return False
    definir_senha(current_user.id, nova_senha)
    flash('Senha alterada com sucesso.', 'success')
    return True


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        username = normalizar_username(request.form.get('username', ''))
        senha = request.form.get('senha', '')
        row = _buscar_row_por_username(username)
        if row and row['ativo'] and check_password_hash(row['senha_hash'], senha):
            login_user(Usuario(row), remember=True)
            flash(f"Bem-vindo(a), {row['nome']}!", 'success')
            next_url = request.args.get('next')
            return redirect(next_url or url_for('main.index'))
        flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Sessão encerrada.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def configuracoes():
    if request.method == 'POST' and request.form.get('acao') == 'trocar_senha':
        if _processar_troca_senha():
            return redirect(url_for('auth.configuracoes'))
        return redirect(url_for('auth.configuracoes'))

    contexto = {
        'title': 'Configurações',
        'pode_gerenciar_formatos': current_user.pode_gerenciar_formatos,
        'formato_edit': None,
        'formatos': [],
        'papeis': (),
        'tol_mapa': {},
    }
    if current_user.pode_gerenciar_formatos:
        from .config import PAPEIS
        from .routes.formatos import _tolerancias_mapa
        from .services.formato_service import listar_formatos_cadastro, obter_formato_por_id

        formato_edit = None
        editar_id = request.args.get('editar')
        if editar_id:
            try:
                formato_edit = obter_formato_por_id(int(editar_id))
            except ValueError:
                formato_edit = None
            if formato_edit is None:
                flash('Formato não encontrado.', 'alert-danger')
                return redirect(url_for('auth.configuracoes'))

        contexto.update({
            'papeis': PAPEIS,
            'formatos': listar_formatos_cadastro(),
            'formato_edit': formato_edit,
            'tol_mapa': _tolerancias_mapa(formato_edit),
        })

    return render_template('configuracoes.html', **contexto)


@auth_bp.route('/trocar-senha', methods=['GET', 'POST'])
@login_required
def trocar_senha():
    """Mantido por compatibilidade; a tela oficial é /configuracoes."""
    if request.method == 'GET':
        return redirect(url_for('auth.configuracoes'))
    if _processar_troca_senha():
        return redirect(url_for('auth.configuracoes'))
    return redirect(url_for('auth.configuracoes'))


@auth_bp.route('/admin/usuarios', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_usuarios():
    if request.method == 'POST':
        acao = request.form.get('acao', 'criar')
        if acao == 'criar':
            username = request.form.get('username', '').strip()
            nome = request.form.get('nome', '').strip()
            senha = request.form.get('senha', '')
            role = request.form.get('role', ROLE_INICIAL)
            if role not in ROLES_VALIDAS:
                role = ROLE_INICIAL
            if not username or not nome:
                flash('Informe usuário e nome.', 'danger')
            elif len(senha) < 4:
                flash('A senha deve ter pelo menos 4 caracteres.', 'danger')
            else:
                ok, mensagem = criar_usuario(username, nome, senha, role)
                flash(mensagem, 'success' if ok else 'danger')
        elif acao == 'resetar_senha':
            user_id = request.form.get('user_id')
            nova_senha = request.form.get('nova_senha_reset', '')
            if len(nova_senha) < 4:
                flash('A nova senha deve ter pelo menos 4 caracteres.', 'danger')
            else:
                definir_senha(user_id, nova_senha)
                flash('Senha redefinida com sucesso.', 'success')
        elif acao == 'alternar_ativo':
            user_id = request.form.get('user_id')
            if str(user_id) == str(current_user.id):
                flash('Você não pode desativar a própria conta.', 'danger')
            else:
                alternar_ativo(user_id)
                flash('Status do usuário atualizado.', 'success')
        return redirect(url_for('auth.admin_usuarios'))

    usuarios = listar_usuarios()
    return render_template('admin_usuarios.html', usuarios=usuarios, role_labels=ROLE_LABELS)


@auth_bp.route('/admin/api-key', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_api_key():
    from .api_auth import obter_api_key, regenerar_api_key

    if request.method == 'POST':
        if os.environ.get('API_KEY'):
            flash('A API key está fixada pela variável de ambiente API_KEY; não é possível regenerar por aqui.', 'danger')
        else:
            regenerar_api_key()
            flash('Nova API key gerada. Integrações que usavam a chave anterior deixarão de funcionar até serem atualizadas.', 'success')
        return redirect(url_for('auth.admin_api_key'))

    return render_template(
        'admin_api_key.html',
        api_key=obter_api_key(),
        fixada_por_env=bool(os.environ.get('API_KEY')),
    )
