"""
Testes da navegação sem reload completo via htmx (Fase 4 da auditoria de
otimização): garantem que uma requisição com o header `HX-Request` recebe só
o fragmento de resultado (tabela + paginação), sem `<html>`/`<head>`/menu, e
que a navegação normal (sem esse header) continua recebendo a página cheia.
"""


def test_historico_sem_hx_request_devolve_pagina_completa(admin_client):
    resp = admin_client.get('/historico')
    assert resp.status_code == 200
    assert b'<html' in resp.data
    assert b'id="historico-resultado"' in resp.data


def test_historico_com_hx_request_devolve_apenas_fragmento(admin_client):
    resp = admin_client.get('/historico', headers={'HX-Request': 'true'})
    assert resp.status_code == 200
    assert b'<html' not in resp.data
    assert b'pagination-bar' in resp.data


def test_historico_fragmento_htmx_respeita_filtro(admin_client):
    resp = admin_client.get('/historico?servico=PYTEST-NAO-EXISTE-XYZ', headers={'HX-Request': 'true'})
    assert resp.status_code == 200
    assert b'Nenhum registro encontrado' in resp.data


def test_pedidos_com_hx_request_devolve_apenas_fragmento(gerente_client):
    full = gerente_client.get('/pedidos')
    assert b'<html' in full.data and b'id="pedidos-resultado"' in full.data

    frag = gerente_client.get('/pedidos', headers={'HX-Request': 'true'})
    assert frag.status_code == 200
    assert b'<html' not in frag.data
    assert b'pagination-bar' in frag.data


def test_movimento_com_hx_request_devolve_apenas_fragmento(gerente_client):
    full = gerente_client.get('/movimento')
    assert b'<html' in full.data and b'id="movimento-resultado"' in full.data

    frag = gerente_client.get('/movimento', headers={'HX-Request': 'true'})
    assert frag.status_code == 200
    assert b'<html' not in frag.data
    assert b'pagination-bar' in frag.data


def test_of_refugo_com_hx_request_devolve_apenas_fragmento(admin_client):
    full = admin_client.get('/of-refugo')
    assert b'<html' in full.data and b'id="of-refugo-resultado"' in full.data

    frag = admin_client.get('/of-refugo', headers={'HX-Request': 'true'})
    assert frag.status_code == 200
    assert b'<html' not in frag.data
    assert b'pagination-bar' in frag.data


def test_comparacao_quantidade_com_hx_request_devolve_apenas_fragmento(admin_client):
    full = admin_client.get('/comparacao-quantidade')
    assert b'<html' in full.data and b'id="comparacao-resultado"' in full.data

    frag = admin_client.get('/comparacao-quantidade', headers={'HX-Request': 'true'})
    assert frag.status_code == 200
    assert b'<html' not in frag.data
    assert b'pagination-bar' in frag.data
