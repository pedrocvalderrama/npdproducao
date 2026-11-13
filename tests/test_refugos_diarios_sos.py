import pytest

from app.routes.lancamento_diario import _montar_registros


@pytest.mark.parametrize('numero', [1, 2, 3, 4])
def test_soma_refugos_sos(numero):
    prefixo = f'sos{numero}'
    linhas = _montar_registros({
        prefixo + '_data': '2026-11-12',
        prefixo + '_refugo_impressora': '12', prefixo + '_refugo_sos': '8',
        prefixo + '_refugo_diario': '999',
    })
    assert len(linhas) == 1
    assert linhas[0]['refugo_diario'] == 20
    assert linhas[0]['refugo_impressora'] == 12
    assert linhas[0]['refugo_sos'] == 8


@pytest.mark.parametrize('valor', ['-1', '1.5', 'abc'])
def test_rejeita_refugo_invalido(valor):
    with pytest.raises(ValueError):
        _montar_registros({'sos1_data': '2026-11-12', 'sos1_refugo_sos': valor})


def test_grava_edita_preserva_legado_e_demais_maquinas(admin_client):
    from app.models import get_db_connection

    conn = get_db_connection()
    try:
        # Isola os registros deste teste sem apagar os demais lançamentos.
        admin_client.post('/lancamento-diario', data={
            'sos1_data': '2040-01-01', 'sos1_refugo_impressora': '10', 'sos1_refugo_sos': '5',
            'impressora_data': '2040-01-01', 'impressora_refugo_diario': '7',
            'robo_data': '2040-01-01', 'robo_refugo_diario': '8',
            'resmadeira_data': '2040-01-01', 'resmadeira_refugo_diario': '9',
            'guilhotina_data': '2040-01-01', 'guilhotina_refugo_diario': '10',
        })
        linhas = {r['equipamento']: dict(r) for r in conn.execute("SELECT * FROM lancamento_diario WHERE data = '2040-01-01'")}
        assert linhas['SOS 1']['refugo_diario'] == 15
        for equip, total in [('IMPRESSORA', 7), ('ROBO', 8), ('RESMADEIRA', 9), ('GUILHOTINA', 10)]:
            assert linhas[equip]['refugo_diario'] == total
            assert linhas[equip]['refugo_sos'] is None
            assert linhas[equip]['refugo_impressora'] is None
        registro = linhas['SOS 1']['id']
        admin_client.post(f'/lancamento-diario/editar/{registro}', data={
            'data': '2040-01-01', 'quantidade': '100', 'refugo_impressora': '', 'refugo_sos': '0',
            'refugo_diario': '999',
        })
        assert conn.execute('SELECT refugo_diario FROM lancamento_diario WHERE id = ?', (registro,)).fetchone()[0] == 0
        conn.execute('UPDATE lancamento_diario SET refugo_impressora = NULL, refugo_sos = NULL, refugo_diario = 25 WHERE id = ?', (registro,))
        conn.commit()
        admin_client.post(f'/lancamento-diario/editar/{registro}', data={
            'data': '2040-01-01', 'quantidade': '100', 'refugo_impressora': '', 'refugo_sos': '',
        })
        assert conn.execute('SELECT refugo_diario FROM lancamento_diario WHERE id = ?', (registro,)).fetchone()[0] == 25
        html = admin_client.get('/historico-diario?filtro_inicio=2040-01-01&filtro_fim=2040-01-01').get_data(as_text=True)
        assert 'Total antigo: 25' in html
        form = admin_client.get('/lancamento-diario').get_data(as_text=True)
        assert 'name="sos1_refugo_diario"' not in form
        assert 'name="sos4_p1_refugo_impressora"' in form
        assert 'name="impressora_p1_refugo_diario"' in form
    finally:
        conn.execute("DELETE FROM lancamento_diario WHERE data = '2040-01-01'")
        conn.commit()
        conn.close()
