import pytest

from app.routes.lancamento_diario import _montar_registros


def formulario(prefixo='sos1'):
    return {prefixo + '_usa_producoes': '1', prefixo + '_data': '2044-01-01'}


def test_soma_producoes_decimal_e_limite():
    form = formulario()
    for i in range(1, 11):
        form.update({f'sos1_p{i}_quantidade': '10', f'sos1_p{i}_milheiro': '125',
                     f'sos1_p{i}_refugo_impressora': '0,1', f'sos1_p{i}_refugo_sos': '0,2'})
    form['sos1_quantidade'] = '99999'  # Totais vindos do cliente são ignorados.
    registro = _montar_registros(form)[0]
    assert registro['quantidade'] == 100
    assert registro['peso_diario'] == 12.5
    assert registro['refugo_diario'] == 3
    assert len(registro['producoes']) == 10
    form['sos1_p11_quantidade'] = '1'
    with pytest.raises(ValueError, match='10 produções'):
        _montar_registros(form)


def test_vazios_textos_e_robo():
    assert _montar_registros(formulario()) == []
    form = formulario('robo')
    form.update(robo_problemas='Parada', robo_p1_quantidade='5', robo_p1_quantidade_alcas='10',
                robo_p1_peso_diario='2,5', robo_p1_refugo_diario='3',
                robo_p6_quantidade='7', robo_p6_quantidade_alcas='14')
    form['robo_quantidade_alcas'] = '24'
    registro = _montar_registros(form)[0]
    assert registro['quantidade'] == 12
    assert registro['quantidade_alcas'] == 24
    assert registro['peso_diario'] is None
    assert registro['refugo_diario'] == 3
    form['robo_p6_quantidade'] = '-1'
    with pytest.raises(ValueError):
        _montar_registros(form)


def test_persistencia_edicao_exclusao_e_erro_sem_perda(admin_client):
    from app.models import get_db_connection
    conn = get_db_connection()
    registro_id = None
    try:
        form = formulario('impressora')
        form.update(impressora_p1_quantidade='100', impressora_p1_peso_diario='10,25',
                    impressora_p1_refugo_diario='1,5', impressora_p7_quantidade='200',
                    impressora_p7_peso_diario='20,5', impressora_p7_refugo_diario='2,5',
                    impressora_meta_diaria='400', impressora_problemas='Uma observação do dia')
        assert admin_client.post('/lancamento-diario', data=form).status_code == 302
        pai = conn.execute("SELECT * FROM lancamento_diario WHERE data = '2044-01-01'").fetchone()
        registro_id = pai['id']
        assert pai['quantidade'] == 300
        assert pai['peso_diario'] is None
        assert pai['refugo_diario'] == 4
        filhos = conn.execute('SELECT * FROM lancamento_diario_producoes WHERE lancamento_id = ? ORDER BY ordem', (registro_id,)).fetchall()
        assert [p['ordem'] for p in filhos] == [1, 7]
        url = f'/lancamento-diario/editar/{registro_id}'
        html = admin_client.get(url).get_data(as_text=True)
        assert 'value="200"' in html
        assert '7 de 10 espaços' in html
        assert 'data-ordem="7" >' in html
        # O total não pode ser alterado diretamente quando há produções detalhadas.
        admin_client.post(url, data={'data': '2044-01-01', 'quantidade': '999'})
        assert conn.execute('SELECT quantidade FROM lancamento_diario WHERE id=?', (registro_id,)).fetchone()[0] == 300
        form['impressora_p1_quantidade'] = '-10'
        erro = admin_client.post(url, data=form)
        assert erro.status_code == 200
        assert 'value="200"' in erro.get_data(as_text=True)
        assert conn.execute('SELECT quantidade FROM lancamento_diario WHERE id=?', (registro_id,)).fetchone()[0] == 300
        form['impressora_p1_quantidade'] = '50'
        admin_client.post(url, data=form)
        assert conn.execute('SELECT quantidade FROM lancamento_diario WHERE id=?', (registro_id,)).fetchone()[0] == 250
        assert conn.execute('SELECT COUNT(*) FROM lancamento_diario_producoes WHERE lancamento_id=?', (registro_id,)).fetchone()[0] == 2
        admin_client.post(f'/lancamento-diario/excluir/{registro_id}')
        assert conn.execute('SELECT COUNT(*) FROM lancamento_diario_producoes WHERE lancamento_id=?', (registro_id,)).fetchone()[0] == 0
    finally:
        if registro_id:
            conn.execute('DELETE FROM lancamento_diario_producoes WHERE lancamento_id=?', (registro_id,))
            conn.execute('DELETE FROM lancamento_diario WHERE id=?', (registro_id,))
            conn.commit()
        conn.close()


def test_alcas_robo_unicas_no_dia_e_campos_peso_removidos(admin_client):
    from app.models import get_db_connection
    conn = get_db_connection()
    registro_id = None
    try:
        form = formulario('robo')
        form.update(robo_quantidade_alcas='50', robo_p1_quantidade='10', robo_p2_quantidade='15',
                    robo_p1_quantidade_alcas='999', robo_p2_quantidade_alcas='999', robo_p1_peso_diario='999')
        admin_client.post('/lancamento-diario', data=form)
        registro = conn.execute("SELECT * FROM lancamento_diario WHERE data = '2044-01-01' AND equipamento = 'ROBO'").fetchone()
        registro_id = registro['id']
        assert registro['quantidade'] == 25
        assert registro['quantidade_alcas'] == 50
        assert registro['peso_diario'] is None
        assert conn.execute('SELECT SUM(quantidade_alcas) FROM lancamento_diario_producoes WHERE lancamento_id=?', (registro_id,)).fetchone()[0] is None
        url = f'/lancamento-diario/editar/{registro_id}'
        html = admin_client.get(url).get_data(as_text=True)
        assert html.count('name="robo_quantidade_alcas"') == 1
        assert 'value="50"' in html
        assert html.index('name="robo_meta_diaria"') < html.index('name="robo_quantidade_alcas"') < html.index('name="robo_p1_quantidade"')
        assert 'name="robo_p1_quantidade_alcas"' not in html
        assert 'name="robo_p1_peso_diario"' not in html
        form['robo_quantidade_alcas'] = '60'
        admin_client.post(url, data=form)
        assert conn.execute('SELECT quantidade_alcas FROM lancamento_diario WHERE id=?', (registro_id,)).fetchone()[0] == 60
        form['robo_quantidade_alcas'] = '-1'
        assert admin_client.post(url, data=form).status_code == 200
        assert conn.execute('SELECT quantidade_alcas FROM lancamento_diario WHERE id=?', (registro_id,)).fetchone()[0] == 60
        novo = admin_client.get('/lancamento-diario').get_data(as_text=True)
        assert 'name="impressora_p1_peso_diario"' not in novo
        assert 'name="resmadeira_p1_peso_diario"' in novo
    finally:
        if registro_id:
            conn.execute('DELETE FROM lancamento_diario_producoes WHERE lancamento_id=?', (registro_id,))
            conn.execute('DELETE FROM lancamento_diario WHERE id=?', (registro_id,))
            conn.commit()
        conn.close()
