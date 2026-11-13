import importlib

import pytest

from app.routes.lancamento_diario import _montar_registros


@pytest.mark.parametrize('numero', [1, 2, 3, 4])
def test_peso_sos_calculado_no_servidor(numero):
    prefixo = f'sos{numero}'
    form = {prefixo + '_usa_producoes': '1', prefixo + '_data': '2045-01-01',
            prefixo + '_p1_quantidade': '2500', prefixo + '_p1_milheiro': '12,5',
            prefixo + '_p1_peso_diario': '999999',
            prefixo + '_p2_quantidade': '1000', prefixo + '_p2_milheiro': '10,75'}
    registro = _montar_registros(form)[0]
    assert registro['producoes'][0]['peso_diario'] == 31.25
    assert registro['producoes'][1]['peso_diario'] == 10.75
    assert registro['peso_diario'] == 42


def test_grava_e_edita_milheiro(admin_client):
    from app.models import get_db_connection
    conn = get_db_connection()
    registro_id = None
    try:
        form = {'sos1_usa_producoes': '1', 'sos1_data': '2045-01-01',
                'sos1_p1_quantidade': '2500', 'sos1_p1_milheiro': '12,5'}
        admin_client.post('/lancamento-diario', data=form)
        registro = conn.execute("SELECT * FROM lancamento_diario WHERE data = '2045-01-01'").fetchone()
        registro_id = registro['id']
        assert registro['peso_diario'] == 31.25
        url = f'/lancamento-diario/editar/{registro_id}'
        html = admin_client.get(url).get_data(as_text=True)
        assert 'Milheiro (kg)' in html
        assert 'name="sos1_p1_peso_diario"' not in html
        assert 'value="12.5"' in html
        form['sos1_p1_milheiro'] = '15,25'
        admin_client.post(url, data=form)
        assert conn.execute('SELECT peso_diario FROM lancamento_diario WHERE id=?', (registro_id,)).fetchone()[0] == 38.125
        filho = conn.execute('SELECT * FROM lancamento_diario_producoes WHERE lancamento_id=?', (registro_id,)).fetchone()
        assert filho['milheiro'] == 15.25
        assert filho['peso_diario'] == 38.125
    finally:
        if registro_id:
            conn.execute('DELETE FROM lancamento_diario_producoes WHERE lancamento_id=?', (registro_id,))
            conn.execute('DELETE FROM lancamento_diario WHERE id=?', (registro_id,))
            conn.commit()
        conn.close()


def test_migracao_preserva_pesos_e_demais_maquinas():
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    migracao = importlib.import_module('migrations.versions.b9c1d3e5f748_milheiro_producoes_sos')
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE lancamento_diario (id INTEGER PRIMARY KEY, equipamento TEXT)')
        conn.exec_driver_sql('CREATE TABLE lancamento_diario_producoes (id INTEGER PRIMARY KEY, lancamento_id INTEGER, quantidade INTEGER, peso_diario REAL)')
        conn.exec_driver_sql("INSERT INTO lancamento_diario VALUES (1, 'SOS 1'), (2, 'IMPRESSORA')")
        conn.exec_driver_sql('INSERT INTO lancamento_diario_producoes VALUES (1, 1, 2000, 25), (2, 1, 0, 10), (3, 2, 2000, 30)')
        with Operations.context(MigrationContext.configure(conn)):
            migracao.upgrade()
        rows = conn.exec_driver_sql('SELECT peso_diario, milheiro FROM lancamento_diario_producoes ORDER BY id').all()
        assert rows == [(25, 12.5), (10, None), (30, None)]
    engine.dispose()
