"""
Testes da API JSON somente leitura (/api/v1/...), adicionada na Fase 4 da
auditoria de otimização. Cobrem os dois caminhos de autenticação (API key e
sessão de login) e a resposta básica das listagens paginadas.
"""
import os


def test_api_sem_autenticacao_retorna_401(client):
    resp = client.get('/api/v1/producao')
    assert resp.status_code == 401
    assert resp.get_json()['erro']


def test_api_com_api_key_invalida_retorna_401(client):
    resp = client.get('/api/v1/producao', headers={'X-API-Key': 'chave-errada'})
    assert resp.status_code == 401


def test_api_com_api_key_valida_funciona(client):
    resp = client.get('/api/v1/producao', headers={'X-API-Key': os.environ['API_KEY']})
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'data' in body and 'total' in body and 'page' in body


def test_api_com_sessao_de_login_funciona(admin_client):
    resp = admin_client.get('/api/v1/producao')
    assert resp.status_code == 200


def test_api_indice_lista_endpoints(admin_client):
    resp = admin_client.get('/api/v1/')
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body['endpoints']) >= 5


def test_api_producao_por_id_inexistente_404(admin_client):
    resp = admin_client.get('/api/v1/producao/999999')
    assert resp.status_code == 404


def test_api_resumo_mensal_formato(admin_client):
    resp = admin_client.get('/api/v1/resumo-mensal?ano=2026')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ano'] == '2026'
    assert isinstance(body['meses'], list)


def test_api_pedidos_e_custos_respondem(admin_client):
    for rota in ('/api/v1/pedidos', '/api/v1/movimento', '/api/v1/custos/papel', '/api/v1/custos/operacionais'):
        resp = admin_client.get(rota)
        assert resp.status_code == 200, f'{rota} retornou {resp.status_code}'


def test_admin_api_key_pagina_acessivel_para_admin(admin_client):
    resp = admin_client.get('/admin/api-key')
    assert resp.status_code == 200
    assert b'X-API-Key' in resp.data


def test_admin_api_key_bloqueada_para_nao_admin(inicial_client):
    resp = inicial_client.get('/admin/api-key', follow_redirects=False)
    assert resp.status_code == 302
