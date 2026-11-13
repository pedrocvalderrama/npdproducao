from datetime import date
import pytest


@pytest.fixture
def config_meta_refugo(app):
    from app.models import get_db_connection
    conn = get_db_connection()
    anterior = conn.execute('SELECT meta_refugo_pct FROM configuracao_quadro_sos WHERE id = 1').fetchone()[0]
    conn.execute('UPDATE configuracao_quadro_sos SET meta_refugo_pct = NULL WHERE id = 1')
    conn.commit()
    try:
        yield conn
    finally:
        conn.execute('UPDATE configuracao_quadro_sos SET meta_refugo_pct = ? WHERE id = 1', (anterior,))
        conn.execute("DELETE FROM lancamento_diario WHERE observacao = 'TESTE-CORES-SOS'")
        conn.commit()
        conn.close()


def test_cores_producao_e_limite_inverso_refugo(admin_client, monkeypatch, config_meta_refugo):
    from app.routes import lancamento_diario as diario
    conn = config_meta_refugo
    conn.executemany(
        '''INSERT INTO lancamento_diario
           (data, equipamento, quantidade, meta_diaria, peso_diario,
            refugo_impressora, refugo_sos, refugo_diario, observacao)
           VALUES ('2043-02-02', ?, ?, ?, ?, ?, 0, ?, 'TESTE-CORES-SOS')''',
        [('SOS 1', 99, 100, 95.001, 4.999, 4.999),
         ('SOS 2', 100, 100, 95, 5, 5),
         ('SOS 3', 101, 100, 94, 6, 6),
         ('SOS 4', 0, 0, None, None, None)],
    )
    conn.commit()
    original = diario._quadro_sos_semana
    quadro = original(date(2043, 2, 2))
    assert quadro['meta_refugo'] == ''
    assert all(r['cor_refugo'] == '' for r in quadro['dias'][0]['maquinas'])

    conn.execute('UPDATE configuracao_quadro_sos SET meta_refugo_pct = 5 WHERE id = 1')
    conn.commit()
    quadro = original(date(2043, 2, 2))
    maquinas = quadro['dias'][0]['maquinas']
    assert quadro['meta_refugo'] == '5'
    assert [r['cor_producao'] for r in maquinas] == ['vermelho', 'verde', 'verde', '']
    assert [r['cor_refugo'] for r in maquinas] == ['verde', 'vermelho', 'vermelho', '']
    assert maquinas[0]['refugo_total_pct'] == '5,00%'  # A comparação precede o arredondamento.
    assert all(r['cor_refugo'] == '' for r in quadro['dias'][1]['maquinas'])
    monkeypatch.setattr(diario, '_quadro_sos_semana', lambda: original(date(2043, 2, 2)))
    html = admin_client.get('/display-diario').get_data(as_text=True)
    quadro_html = html.split('id="indicadores-sos"', 1)[1].split('<script', 1)[0]
    assert quadro_html.count('sos-refugo refugo-vermelho') == 2
    assert quadro_html.count('sos-refugo refugo-verde') == 1
    assert 'Abaixo da meta' in quadro_html
    assert 'Meta &lt; 5%' in quadro_html
    assert 'value="5"' in quadro_html

    conn.execute('UPDATE configuracao_quadro_sos SET meta_refugo_pct = 0 WHERE id = 1')
    conn.execute("UPDATE lancamento_diario SET peso_diario = 100, refugo_impressora = 0, refugo_diario = 0 WHERE observacao = 'TESTE-CORES-SOS' AND equipamento = 'SOS 1'")
    conn.commit()
    quadro = original(date(2043, 2, 2))
    assert quadro['meta_refugo'] == '0'
    assert quadro['dias'][0]['maquinas'][0]['cor_refugo'] == 'vermelho'


@pytest.mark.parametrize('entrada,esperado', [('5', 5), ('5,5', 5.5), ('5.5', 5.5), ('0', 0), ('100', 100), ('', None)])
def test_salvar_meta_refugo_compartilhada(admin_client, config_meta_refugo, entrada, esperado):
    conn = config_meta_refugo
    conn.execute('UPDATE configuracao_quadro_sos SET meta_refugo_pct = 10 WHERE id = 1')
    conn.commit()
    antes = admin_client.get('/display-diario/versao').get_json()['versao']
    resposta = admin_client.post('/display-diario/meta-refugo-sos', data={
        'meta_refugo': entrada, 'mes': '2043-02', 'data': '2043-02-02',
    })
    assert resposta.status_code == 302
    assert 'mes=2043-02' in resposta.location and 'data=2043-02-02' in resposta.location
    assert resposta.location.endswith('#indicadores-sos')
    assert conn.execute('SELECT meta_refugo_pct FROM configuracao_quadro_sos WHERE id = 1').fetchone()[0] == esperado
    assert admin_client.get('/display-diario/versao').get_json()['versao'] > antes


@pytest.mark.parametrize('entrada', ['-1', '101', '5%', 'NaN', 'inf', 'abc', '1,2,3'])
def test_meta_refugo_invalida_preserva_valor(admin_client, config_meta_refugo, entrada):
    conn = config_meta_refugo
    conn.execute('UPDATE configuracao_quadro_sos SET meta_refugo_pct = 5 WHERE id = 1')
    conn.commit()
    antes = admin_client.get('/display-diario/versao').get_json()['versao']
    resposta = admin_client.post('/display-diario/meta-refugo-sos', data={'meta_refugo': entrada})
    assert resposta.status_code == 302
    assert conn.execute('SELECT meta_refugo_pct FROM configuracao_quadro_sos WHERE id = 1').fetchone()[0] == 5
    assert admin_client.get('/display-diario/versao').get_json()['versao'] == antes

def test_display_sos_formulas_filtros_e_dados_ausentes(admin_client, monkeypatch):
    from app.models import get_db_connection
    from app.routes import lancamento_diario as diario

    conn = get_db_connection()
    try:
        conn.executemany(
            '''INSERT INTO lancamento_diario
               (data, equipamento, quantidade, meta_diaria, peso_diario,
                refugo_impressora, refugo_sos, refugo_diario, observacao)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'TESTE-QUADRO-SOS')''',
            [
                ('2026-09-28', 'SOS 1', 800, 1000, 900, 100, 50, 150),
                ('2026-09-28', 'SOS 1', 200, 100, 100, 0, 0, 0),
                ('2026-09-29', 'SOS 2', 0, 0, None, None, None, None),
                ('2026-09-30', 'SOS 3', 500, 1000, 80, None, None, 20),
                ('2026-10-01', 'SOS 4', 10, 100, 0, 0, 0, 0),
                ('2026-10-02', 'SOS 4', 10, 100, 100, 10, None, 10),
                ('2026-09-28', 'IMPRESSORA', 999, 1000, None, None, None, 30),
                ('2026-09-28', 'ROBO', 999, 1000, None, None, None, 30),
                ('2026-10-03', 'SOS 1', 999, 1000, 100, 10, 10, 20),
                ('2041-09-01', 'SOS 1', 999, 1000, 100, 10, 10, 20),
            ],
        )
        conn.commit()
        original = diario._quadro_sos_semana
        quadro = original(date(2026, 9, 30))
        assert quadro['inicio'] == '28/09/2026'
        assert quadro['fim'] == '02/10/2026'
        assert len(quadro['dias']) == 5
        assert all(len(d['maquinas']) == 4 for d in quadro['dias'])
        linhas = [r for d in quadro['dias'] for r in d['maquinas'] if r['tem_dados']]
        assert len(linhas) == 5
        calculada = quadro['dias'][0]['maquinas'][0]
        assert calculada['producao'] == '1.000'
        assert calculada['produtividade'] == '90,91%'
        assert calculada['refugo'] == '150,00'
        assert calculada['refugo_pi_pct'] == '9,09%'
        assert calculada['refugo_sos_pct'] == '4,76%'
        assert calculada['refugo_total_pct'] == '13,04%'
        zerada = next(r for r in linhas if r['sos'] == 'SOS 2')
        assert zerada['produtividade'] == zerada['refugo_pi_pct'] == zerada['refugo_total_pct'] == '—'
        antiga = next(r for r in linhas if r['sos'] == 'SOS 3')
        assert antiga['refugo'] == '20,00'
        assert antiga['refugo_pi_pct'] == antiga['refugo_sos_pct'] == '—'
        assert antiga['refugo_total_pct'] == '20,00%'
        peso_zero = quadro['dias'][3]['maquinas'][3]
        assert peso_zero['refugo_total_pct'] == '—'
        parcial = quadro['dias'][4]['maquinas'][3]
        assert parcial['refugo_sos_pct'] == '0,00%'
        assert parcial['refugo_total_pct'] == '9,09%'
        assert quadro['dias'][2]['hoje']
        assert quadro['dias'][3]['futuro']
        assert not quadro['dias'][4]['maquinas'][0]['tem_dados']
        assert original(date(2026, 10, 4))['inicio'] == '28/09/2026'
        assert original(date(2027, 1, 1))['inicio'] == '28/12/2026'
        monkeypatch.setattr(diario, '_quadro_sos_semana', lambda: original(date(2026, 9, 30)))
        html = admin_client.get('/display-diario?mes=2042-09&data=2042-10-01').get_data(as_text=True)
        assert html.index('id="indicadores-sos"') > html.index('id="painel-tv"')
        tabela = html.split('id="indicadores-sos"', 1)[1]
        assert '90,91%' in tabela
        assert '28/09/2026 a 02/10/2026' in tabela
        assert 'SOS 1' in tabela and 'SOS 4' in tabela
        assert tabela.count('<article class="sos-maquina') == 20
    finally:
        conn.execute("DELETE FROM lancamento_diario WHERE observacao = 'TESTE-QUADRO-SOS'")
        conn.commit()
        conn.close()
