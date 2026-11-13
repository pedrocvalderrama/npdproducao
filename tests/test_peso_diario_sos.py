import pytest

from app.routes.lancamento_diario import _montar_registros, _parse_peso_diario


@pytest.mark.parametrize('entrada, esperado', [('1250,75', 1250.75), ('12.345', 12.345), ('0', 0), ('', None)])
def test_peso_decimal(entrada, esperado):
    assert _parse_peso_diario(entrada, 'SOS 1') == esperado


@pytest.mark.parametrize('entrada', ['-1', 'abc', 'NaN', 'Infinity', '1,2,3'])
def test_peso_invalido(entrada):
    with pytest.raises(ValueError):
        _parse_peso_diario(entrada, 'SOS 1')


@pytest.mark.parametrize('numero', [1, 2, 3, 4])
def test_peso_sozinho_gera_lancamento(numero):
    registros = _montar_registros({f'sos{numero}_peso_diario': '10,5', f'sos{numero}_data': '2026-11-12'})
    assert registros[0]['peso_diario'] == 10.5


def test_grava_e_edita_peso(admin_client):
    from app.models import get_db_connection

    conn = get_db_connection()
    try:
        response = admin_client.post('/lancamento-diario', data={
            'sos1_peso_diario': '123,456', 'sos1_data': '2041-01-01',
            'impressora_peso_diario': '999', 'impressora_quantidade': '1', 'impressora_data': '2041-01-01',
        })
        assert response.status_code == 302
        registro = conn.execute("SELECT * FROM lancamento_diario WHERE data = '2041-01-01' AND equipamento = 'SOS 1'").fetchone()
        assert registro['peso_diario'] == pytest.approx(123.456)
        assert conn.execute("SELECT peso_diario FROM lancamento_diario WHERE data = '2041-01-01' AND equipamento = 'IMPRESSORA'").fetchone()[0] is None
        admin_client.post(f'/lancamento-diario/editar/{registro["id"]}', data={
            'data': '2041-01-01', 'quantidade': '0', 'peso_diario': '150,75',
        })
        assert conn.execute('SELECT peso_diario FROM lancamento_diario WHERE id = ?', (registro['id'],)).fetchone()[0] == 150.75
        html = admin_client.get('/historico-diario?filtro_inicio=2041-01-01&filtro_fim=2041-01-01').get_data(as_text=True)
        assert '150,75' in html
        assert 'Peso Diário (kg)' in html
        admin_client.post(f'/lancamento-diario/editar/{registro["id"]}', data={
            'data': '2041-01-01', 'quantidade': '0', 'peso_diario': '-5',
        })
        assert conn.execute('SELECT peso_diario FROM lancamento_diario WHERE id = ?', (registro['id'],)).fetchone()[0] == 150.75
    finally:
        conn.execute("DELETE FROM lancamento_diario WHERE data = '2041-01-01'")
        conn.commit()
        conn.close()
