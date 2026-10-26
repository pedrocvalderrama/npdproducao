"""Aba Lançamento Diário: grava em `lancamento_diario` sem tocar em `producao`."""


def _linhas(app, sql, params=()):
    with app.app_context():
        from app.models import get_db_connection
        conn = get_db_connection()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()


def _limpar(app):
    with app.app_context():
        from app.models import get_db_connection
        conn = get_db_connection()
        conn.execute('DELETE FROM lancamento_diario')
        conn.commit()
        conn.close()


def test_salva_apenas_blocos_preenchidos_e_nao_toca_em_producao(admin_client, app):
    _limpar(app)
    total_producao_antes = _linhas(app, 'SELECT COUNT(*) AS n FROM producao')[0]['n']
    try:
        resp = admin_client.post('/lancamento-diario', data={
            'sos1_quantidade': '1500',
            'sos1_data': '2026-09-28',
            'sos1_problemas': 'Faca travando',
            'sos2_quantidade': '',
            'sos2_data': '2026-09-28',
            'impressora_quantidade': '2200',
            'impressora_data': '2026-09-28',
            'robo_quantidade': '800',
            'robo_quantidade_alcas': '1600',
            'robo_data': '28/09/2026',
            'guilhotina_data': '2026-09-28',
            'guilhotina_observacao': 'Parada para manutenção',
        }, follow_redirects=True)
        assert resp.status_code == 200

        linhas = _linhas(app, 'SELECT * FROM lancamento_diario ORDER BY equipamento')
        por_equip = {r['equipamento']: r for r in linhas}
        assert set(por_equip) == {'SOS 1', 'IMPRESSORA', 'ROBO', 'GUILHOTINA'}
        assert por_equip['IMPRESSORA']['quantidade'] == 2200
        assert por_equip['IMPRESSORA']['quantidade_alcas'] is None
        assert por_equip['SOS 1']['quantidade'] == 1500
        assert por_equip['SOS 1']['data'] == '2026-09-28'
        assert por_equip['SOS 1']['problemas'] == 'Faca travando'
        assert por_equip['SOS 1']['quantidade_alcas'] is None
        assert por_equip['ROBO']['quantidade'] == 800
        assert por_equip['ROBO']['quantidade_alcas'] == 1600
        assert por_equip['ROBO']['data'] == '2026-09-28'
        assert por_equip['GUILHOTINA']['quantidade'] == 0

        total_producao_depois = _linhas(app, 'SELECT COUNT(*) AS n FROM producao')[0]['n']
        assert total_producao_depois == total_producao_antes
    finally:
        _limpar(app)


def test_quantidade_invalida_nao_grava_nada(admin_client, app):
    _limpar(app)
    resp = admin_client.post('/lancamento-diario', data={
        'sos1_quantidade': '100',
        'sos1_data': '2026-09-28',
        'sos3_quantidade': '12,5',
        'sos3_data': '2026-09-28',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert 'número inteiro'.encode('utf-8') in resp.data
    assert _linhas(app, 'SELECT * FROM lancamento_diario') == []


def test_display_diario_mostra_so_sacolas_do_robo_e_filtra_pela_data(admin_client, app):
    _limpar(app)
    try:
        admin_client.post('/lancamento-diario', data={
            'sos1_quantidade': '1000', 'sos1_data': '2026-09-28', 'sos1_problemas': 'Faca travando',
            'robo_quantidade': '777', 'robo_quantidade_alcas': '99999', 'robo_data': '2026-09-28',
            'sos2_quantidade': '555', 'sos2_data': '2026-09-27',
        }, follow_redirects=True)
        admin_client.post('/lancamento-diario', data={
            'sos1_quantidade': '500', 'sos1_data': '2026-09-28', 'sos1_problemas': 'Papel rasgando',
        }, follow_redirects=True)

        html = admin_client.get('/display-diario?data=2026-09-28').get_data(as_text=True)
        assert '28/09/2026' in html
        assert '1.500' in html
        assert 'Faca travando\nPapel rasgando' in html
        assert '777' in html
        assert '99.999' not in html and '99999' not in html
        assert '555' not in html
    finally:
        _limpar(app)


def _limpar_metas(app):
    with app.app_context():
        from app.models import get_db_connection
        conn = get_db_connection()
        conn.execute('DELETE FROM metas_lancamento_diario')
        conn.commit()
        conn.close()


def test_meta_do_mes_soma_grupos_e_compara_com_meta(admin_client, app):
    _limpar(app)
    _limpar_metas(app)
    try:
        admin_client.post('/lancamento-diario', data={
            'sos1_quantidade': '1000', 'sos1_data': '2026-09-01',
            'sos4_quantidade': '500', 'sos4_data': '2026-09-30',
            'impressora_quantidade': '3000', 'impressora_data': '2026-09-15',
            'robo_quantidade': '400', 'robo_quantidade_alcas': '800', 'robo_data': '2026-09-10',
            'guilhotina_quantidade': '9999', 'guilhotina_data': '2026-09-10',
        }, follow_redirects=True)
        # Sábado 05/09/2026: não deve entrar na Meta do Mês / painel TV
        admin_client.post('/lancamento-diario', data={
            'sos3_quantidade': '9999', 'sos3_data': '2026-09-05',
            'impressora_quantidade': '8888', 'impressora_data': '2026-09-05',
            'robo_quantidade': '7777', 'robo_quantidade_alcas': '1', 'robo_data': '2026-09-05',
        }, follow_redirects=True)
        admin_client.post('/lancamento-diario', data={
            'sos2_quantidade': '7777', 'sos2_data': '2026-10-01',
        }, follow_redirects=True)

        resp = admin_client.post('/display-diario/metas', data={
            'mes': '2026-09', 'meta_SOS': '3000', 'meta_IMPRESSORA': '2000', 'meta_ROBO': '',
        }, follow_redirects=True)
        assert resp.status_code == 200

        metas = _linhas(app, 'SELECT grupo, meta_quantidade FROM metas_lancamento_diario WHERE ano = 2026 AND mes = 9')
        assert {m['grupo']: m['meta_quantidade'] for m in metas} == {'SOS': 3000, 'IMPRESSORA': 2000}

        from datetime import date
        from app.routes.lancamento_diario import _montar_meta_mes
        with app.app_context():
            # Setembro já encerrado: projeção = produzido (22/22 úteis)
            linhas = {r['grupo']: r for r in _montar_meta_mes(2026, 9, hoje=date(2026, 10, 19))}
            # No dia 10/09/2026 (qui): 8 úteis decorridos de 22 no mês → × 22/8
            linhas_dia10 = {r['grupo']: r for r in _montar_meta_mes(2026, 9, hoje=date(2026, 9, 10))}
        assert set(linhas) == {'SOS', 'IMPRESSORA', 'ROBO'}
        assert linhas['SOS']['produzido_fmt'] == '1.500'
        assert linhas['SOS']['status_fmt'] == '50,00%'
        assert linhas['SOS']['falta_fmt'] == '1.500'
        assert linhas['SOS']['pct_grafico'] == 50.0
        assert linhas['SOS']['projecao_fmt'] == '1.500'
        assert linhas['IMPRESSORA']['atingida'] is True
        assert linhas['IMPRESSORA']['pct_grafico'] == 100.0
        assert linhas['IMPRESSORA']['falta_fmt'] == '0'
        assert linhas['IMPRESSORA']['projecao_fmt'] == '3.000'
        assert linhas['ROBO']['produzido_fmt'] == '400'
        assert linhas['ROBO']['meta_fmt'] == '—'
        assert linhas['ROBO']['projecao_fmt'] == '400'
        assert linhas_dia10['SOS']['projecao_fmt'] == '4.125'  # 1500 * 22 / 8
        assert linhas_dia10['IMPRESSORA']['projecao_fmt'] == '8.250'  # 3000 * 22 / 8
        assert linhas_dia10['ROBO']['projecao_fmt'] == '1.100'  # 400 * 22 / 8

        html = admin_client.get('/display-diario?mes=2026-09').get_data(as_text=True)
        assert 'Setembro/2026' in html
        assert 'Projeção Calculada' in html.split('Meta do Mês')[1]
        assert 'Guilhotina' not in html.split('Meta do Mês')[1]
        assert 'stroke-dasharray="50.00 100"' in html
        assert 'Sem meta' in html

        admin_client.post('/display-diario/metas', data={
            'mes': '2026-09', 'meta_SOS': '3500', 'meta_IMPRESSORA': '0', 'meta_ROBO': '100',
        }, follow_redirects=True)
        metas = _linhas(app, 'SELECT grupo, meta_quantidade FROM metas_lancamento_diario WHERE ano = 2026 AND mes = 9')
        assert {m['grupo']: m['meta_quantidade'] for m in metas} == {'SOS': 3500, 'ROBO': 100}
    finally:
        _limpar(app)
        _limpar_metas(app)


def test_editar_lancamento_diario_na_linha(admin_client, app):
    _limpar(app)
    try:
        admin_client.post('/lancamento-diario', data={
            'sos1_quantidade': '100', 'sos1_data': '2026-09-28',
            'robo_quantidade': '50', 'robo_quantidade_alcas': '100', 'robo_data': '2026-09-28',
        }, follow_redirects=True)
        ids = {r['equipamento']: r['id'] for r in _linhas(app, 'SELECT id, equipamento FROM lancamento_diario')}

        resp = admin_client.post(f"/lancamento-diario/editar/{ids['SOS 1']}", data={
            'data': '2026-09-29', 'quantidade': '150', 'quantidade_alcas': '999',
            'problemas': 'Corrigido', 'solucoes': '', 'observacao': 'Obs nova',
            'voltar_para': '/historico-diario?page=1',
        })
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/historico-diario?page=1')

        sos1 = _linhas(app, 'SELECT * FROM lancamento_diario WHERE id = ?', (ids['SOS 1'],))[0]
        assert (sos1['data'], sos1['quantidade'], sos1['quantidade_alcas']) == ('2026-09-29', 150, None)
        assert (sos1['problemas'], sos1['solucoes'], sos1['observacao']) == ('Corrigido', None, 'Obs nova')

        admin_client.post(f"/lancamento-diario/editar/{ids['ROBO']}", data={
            'data': '2026-09-28', 'quantidade': '60', 'quantidade_alcas': '120',
        })
        robo = _linhas(app, 'SELECT * FROM lancamento_diario WHERE id = ?', (ids['ROBO'],))[0]
        assert (robo['quantidade'], robo['quantidade_alcas']) == (60, 120)

        resp = admin_client.post(f"/lancamento-diario/editar/{ids['ROBO']}", data={
            'data': '2026-09-28', 'quantidade': '1,5',
        }, follow_redirects=True)
        assert 'número inteiro'.encode('utf-8') in resp.data
        assert _linhas(app, 'SELECT quantidade FROM lancamento_diario WHERE id = ?', (ids['ROBO'],))[0]['quantidade'] == 60

        resp = admin_client.post(f"/lancamento-diario/editar/{ids['ROBO']}", data={
            'data': '2026-09-28', 'quantidade': '60', 'voltar_para': 'https://site-externo.com',
        })
        assert resp.headers['Location'].endswith('/historico-diario')
    finally:
        _limpar(app)


def test_listagem_filtra_por_data_e_pagina(admin_client, app):
    from app.routes.lancamento_diario import REGISTROS_POR_PAGINA
    _limpar(app)
    try:
        with app.app_context():
            from app.models import get_db_connection
            conn = get_db_connection()
            conn.executemany(
                "INSERT INTO lancamento_diario (data, equipamento, quantidade, observacao) VALUES (?, 'SOS 1', 1, ?)",
                [('2026-08-15', f'AGOSTO-{i}') for i in range(3)]
                + [('2026-09-10', f'SETEMBRO-{i}') for i in range(REGISTROS_POR_PAGINA + 5)],
            )
            conn.commit()
            conn.close()

        html_form = admin_client.get('/lancamento-diario').get_data(as_text=True)
        assert 'Lançamento Diário' in html_form
        assert 'class="linha-diario"' not in html_form

        html = admin_client.get('/historico-diario').get_data(as_text=True)
        assert 'Histórico Diário' in html
        assert f'{REGISTROS_POR_PAGINA + 8} registro(s) encontrado(s) — página 1 de 2' in html

        html = admin_client.get('/historico-diario?filtro_inicio=2026-08-01&filtro_fim=2026-08-31').get_data(as_text=True)
        assert '3 registro(s) encontrado(s) — página 1 de 1' in html
        assert 'AGOSTO-0' in html and 'SETEMBRO-0' not in html

        html = admin_client.get('/historico-diario?filtro_inicio=2026-09-01&page=2').get_data(as_text=True)
        assert 'página 2 de 2' in html
        assert html.count('class="linha-diario"') == 5
    finally:
        _limpar(app)


def test_excluir_lancamento_diario(admin_client, app):
    _limpar(app)
    admin_client.post('/lancamento-diario', data={
        'resmadeira_quantidade': '300',
        'resmadeira_data': '2026-09-28',
    }, follow_redirects=True)
    linhas = _linhas(app, 'SELECT id FROM lancamento_diario')
    assert len(linhas) == 1

    resp = admin_client.post(f"/lancamento-diario/excluir/{linhas[0]['id']}", follow_redirects=True)
    assert resp.status_code == 200
    assert _linhas(app, 'SELECT * FROM lancamento_diario') == []


def test_versao_painel_sobe_a_cada_lancamento(admin_client, app):
    _limpar(app)
    try:
        v0 = admin_client.get('/display-diario/versao').get_json()['versao']
        admin_client.post('/lancamento-diario', data={
            'sos1_quantidade': '100', 'sos1_data': '2026-09-28',
        }, follow_redirects=True)
        v1 = admin_client.get('/display-diario/versao').get_json()['versao']
        assert v1 > v0

        ids = _linhas(app, 'SELECT id FROM lancamento_diario')
        admin_client.post(f"/lancamento-diario/editar/{ids[0]['id']}", data={
            'data': '2026-09-28', 'quantidade': '150',
        })
        v2 = admin_client.get('/display-diario/versao').get_json()['versao']
        assert v2 > v1

        admin_client.post(f"/lancamento-diario/excluir/{ids[0]['id']}", follow_redirects=True)
        v3 = admin_client.get('/display-diario/versao').get_json()['versao']
        assert v3 > v2
    finally:
        _limpar(app)
