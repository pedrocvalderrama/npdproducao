"""
Testes de regressão (smoke tests) das rotas críticas, usados como rede de
segurança durante a refatoração estrutural (Fase 3). O objetivo não é cobertura
completa, e sim garantir que nenhuma extração de código mude o comportamento
observável: status HTTP, redirecionamentos de autenticação/autorização e o
ciclo básico de lançar/editar/excluir produção continuam funcionando.
"""


def test_pagina_protegida_sem_login_redireciona(client):
    resp = client.get('/historico', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_login_com_senha_errada_falha(client):
    resp = client.post('/login', data={'username': 'admin', 'senha': 'errada'}, follow_redirects=True)
    assert 'inv\u00e1lidos'.encode('utf-8') in resp.data or b'invalidos' in resp.data


def test_login_com_senha_correta_funciona(client):
    resp = client.post('/login', data={'username': 'admin', 'senha': 'admin123'}, follow_redirects=True)
    assert resp.status_code == 200
    resp2 = client.get('/historico')
    assert resp2.status_code == 200


PAGINAS_PRINCIPAIS = [
    '/',
    '/historico',
    '/pedidos',
    '/movimento',
    '/of-refugo',
    '/comparacao-quantidade',
    '/comparativo-mensal',
    '/analise',
    '/lancamento-diario',
    '/display-diario',
    '/custo',
    '/configurar_custos',
    '/configurar_custo_operacional',
    '/configuracoes',
    '/admin/usuarios',
]


def test_todas_paginas_principais_ok_para_admin(admin_client):
    for url in PAGINAS_PRINCIPAIS:
        resp = admin_client.get(url)
        assert resp.status_code == 200, f'{url} retornou {resp.status_code}'


def test_papel_inicial_nao_acessa_pedidos_e_movimento(inicial_client):
    for url in ('/pedidos', '/movimento'):
        resp = inicial_client.get(url, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers['Location'].rstrip('/').endswith('8082') is False  # sanity: é um path relativo

    # continua acessando produção e custos normalmente
    for url in ('/', '/historico', '/custo'):
        resp = inicial_client.get(url)
        assert resp.status_code == 200

    # não acessa a administração de usuários
    resp = inicial_client.get('/admin/usuarios', follow_redirects=False)
    assert resp.status_code == 302


def test_papel_gerente_acessa_pedidos_e_movimento(gerente_client):
    for url in ('/pedidos', '/movimento'):
        resp = gerente_client.get(url)
        assert resp.status_code == 200

    # gerente não é admin
    resp = gerente_client.get('/admin/usuarios', follow_redirects=False)
    assert resp.status_code == 302


def test_configuracoes_senha_para_todos_e_formatos_para_gerente(inicial_client, gerente_client, admin_client):
    html_inicial = inicial_client.get('/configuracoes').get_data(as_text=True)
    assert 'Trocar Senha' in html_inicial
    assert 'Cadastrar Novo Formato' not in html_inicial
    assert inicial_client.get('/configuracoes/formatos', follow_redirects=False).status_code == 302

    html_gerente = gerente_client.get('/configuracoes').get_data(as_text=True)
    assert 'Trocar Senha' in html_gerente
    assert 'Cadastrar Novo Formato' in html_gerente
    assert gerente_client.get('/configuracoes/formatos', follow_redirects=False).status_code == 302
    assert '/configuracoes' in gerente_client.get('/configuracoes/formatos', follow_redirects=False).headers['Location']

    html_admin = admin_client.get('/configuracoes').get_data(as_text=True)
    assert 'Trocar Senha' in html_admin
    assert 'Cadastrar Novo Formato' in html_admin


def _payload_lancamento(num_of):
    return {
        'num_of': num_of,
        'numero_pedido': '12345',
        'data': '2026-01-01',
        'operador': 'JOSÉ',
        'sos': 'SOS 1',
        'tipo': 'SACOLA',
        'formato': '18X25X10',
        'papel': 'BRANCO 110G',
        'servico': 'TESTE PYTEST',
        'milheiro': '10',
        'tipo_impressao': 'SOS',
        'qtd_cliches': '1',
        'quantidade_comanda': '1000',
        'quantidade': '1000',
        'quantidade_inspecao_geral': '950',
        'refugo_flexo': '0',
        'refugo_pre_impresso': '0',
        'refugo_sos': '0',
        'refugo_acerto_flexo': '0',
        'refugo_acerto_sos': '0',
        'refugo_robo': '0',
        'refugo_inspecao_final': '0',
    }


def test_quantidade_robo_exige_robo_alca(admin_client, app):
    num_of = 'PYTEST-ROBO-001'
    payload = _payload_lancamento(num_of)
    payload['quantidade_robo'] = '100'
    payload['robo_alca'] = ''

    resp = admin_client.post('/lancar', data=payload, follow_redirects=True)
    assert resp.status_code == 200
    assert 'obrigatório selecionar o Robô Alça'.encode('utf-8') in resp.data
    with app.app_context():
        from app.models import get_db_connection
        conn = get_db_connection()
        try:
            assert conn.execute("SELECT COUNT(*) AS n FROM producao WHERE num_of = ?", (num_of,)).fetchone()['n'] == 0
        finally:
            conn.close()

    payload['robo_alca'] = 'APLA-2R'
    resp = admin_client.post('/lancar', data=payload, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        from app.models import get_db_connection
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT quantidade_robo, robo_alca FROM producao WHERE num_of = ?", (num_of,)).fetchone()
            assert row is not None
            assert row['quantidade_robo'] == 100
            assert row['robo_alca'] == 'APLA-2R'
            conn.execute("DELETE FROM producao WHERE num_of = ?", (num_of,))
            conn.commit()
        finally:
            conn.close()


def test_ciclo_lancar_editar_excluir_producao(admin_client, app):
    num_of = 'PYTEST-0001'

    resp = admin_client.post('/lancar', data=_payload_lancamento(num_of), follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        from app.models import get_db_connection
        conn = get_db_connection()
        row = conn.execute('SELECT * FROM producao WHERE num_of = ?', (num_of,)).fetchone()
        conn.close()
    assert row is not None, 'Registro não foi criado por /lancar'
    registro_id = row['id']

    payload_editado = _payload_lancamento(num_of)
    payload_editado['servico'] = 'TESTE PYTEST EDITADO'
    resp = admin_client.post(f'/editar/{registro_id}', data=payload_editado, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        from app.models import get_db_connection
        conn = get_db_connection()
        row2 = conn.execute('SELECT servico FROM producao WHERE id = ?', (registro_id,)).fetchone()
        conn.close()
    assert row2['servico'] == 'TESTE PYTEST EDITADO'

    resp = admin_client.post(f'/excluir/{registro_id}', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        from app.models import get_db_connection
        conn = get_db_connection()
        row3 = conn.execute('SELECT * FROM producao WHERE id = ?', (registro_id,)).fetchone()
        conn.close()
    assert row3 is None, 'Registro não foi removido por /excluir'


def test_lancar_com_num_of_existente_faz_upsert_sem_duplicar(admin_client, app):
    """/lancar reenviado com o mesmo num_of deve atualizar o registro (não criar outro)."""
    num_of = 'PYTEST-UPSERT-0001'
    try:
        payload = _payload_lancamento(num_of)
        resp = admin_client.post('/lancar', data=payload, follow_redirects=True)
        assert resp.status_code == 200

        payload2 = _payload_lancamento(num_of)
        payload2['servico'] = 'TESTE PYTEST UPSERT'
        resp2 = admin_client.post('/lancar', data=payload2, follow_redirects=True)
        assert resp2.status_code == 200

        with app.app_context():
            from app.models import get_db_connection
            conn = get_db_connection()
            linhas = conn.execute('SELECT * FROM producao WHERE num_of = ?', (num_of,)).fetchall()
            conn.close()
        assert len(linhas) == 1, f'Esperava 1 registro para {num_of}, encontrou {len(linhas)}'
        assert linhas[0]['servico'] == 'TESTE PYTEST UPSERT'
    finally:
        with app.app_context():
            from app.models import get_db_connection
            conn = get_db_connection()
            conn.execute('DELETE FROM producao WHERE num_of = ?', (num_of,))
            conn.commit()
            conn.close()
