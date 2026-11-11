from io import BytesIO
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from app.business import calc_tempo_producao_robo


def test_tempo_robo_quatro_dias_e_virada_de_dia():
    assert calc_tempo_producao_robo({}) == 0
    assert calc_tempo_producao_robo({'inicio_prod_robo': '08:00'}) == 0
    assert calc_tempo_producao_robo({
        'inicio_prod_robo': '22:00', 'fim_prod_robo': '02:00',
        'inicio_prod_robo_2': '08:00', 'fim_prod_robo_2': '09:30',
        'inicio_prod_robo_3': '10:00', 'fim_prod_robo_3': '12:00',
        'inicio_prod_robo_4': '14:00', 'fim_prod_robo_4': '15:00',
    }) == 30600


def test_lancar_editar_historico_e_excel_robo(admin_client):
    from app.models import get_db_connection

    num_of = 'TESTE-HORARIOS-ROBO'
    form = {
        'num_of': num_of, 'servico': 'Teste horários Robô',
        'data_robo': '2026-11-11', 'robo_alca': 'APLA-2R', 'quantidade_robo': '1000',
        'inicio_prod_robo': '22:00', 'fim_prod_robo': '02:00',
        'inicio_prod_robo_2': '08:00', 'fim_prod_robo_2': '09:30',
        'inicio_prod_robo_3': '10:00', 'fim_prod_robo_3': '12:00',
        'inicio_prod_robo_4': '14:00', 'fim_prod_robo_4': '15:00',
    }
    try:
        assert admin_client.post('/lancar', data=form).status_code == 302
        conn = get_db_connection()
        try:
            salvo = dict(conn.execute('SELECT * FROM producao WHERE num_of = ?', (num_of,)).fetchone())
        finally:
            conn.close()
        assert salvo['tempo_prod_robo'] == 30600
        assert salvo['fim_prod_robo_4'] == '15:00'
        html = admin_client.get(f'/editar/{salvo["id"]}').get_data(as_text=True)
        for dia in range(1, 5):
            assert f'Início Produção Robô (Dia {dia})' in html
            assert f'Fim Produção Robô (Dia {dia})' in html
        assert 'value="15:00"' in html
        for dia in (2, 3, 4):
            assert f'id="add_robo_day_{dia}"' in html
        dados_of = admin_client.get('/buscar_por_of', query_string={'num_of': num_of})
        # O preenchimento por OF devolve os novos campos junto dos demais dados.
        assert dados_of.status_code == 200
        assert dados_of.get_json()['fim_prod_robo_4'] == '15:00'

        historico = admin_client.get('/historico', query_string={'num_of': num_of}).get_data(as_text=True)
        assert 'Tempo Produção Robô' in historico
        assert '08:30:00' in historico
        assert 'Início Produção Robô (Dia 1)' in historico
        assert 'Fim Produção Robô (Dia 1)' in historico
        assert 'Início Produção Robô (Dia 4)' not in historico
        assert 'Velocidade Robô' in historico
        assert '%.2f' % (1000 / 510) in historico
        for dia in (2, 3, 4):
            assert f'Início Produção Robô (Dia {dia})' not in historico
            assert f'Fim Produção Robô (Dia {dia})' not in historico
        assert admin_client.get('/historico', query_string={
            'num_of': num_of, 'sort_by': 'velocidade_un_min_robo', 'sort_order': 'asc',
        }).status_code == 200
        export = admin_client.get('/historico', query_string={'num_of': num_of, 'export': 'excel'})
        assert export.status_code == 200
        with ZipFile(BytesIO(export.data)) as arquivo:
            strings = ET.fromstring(arquivo.read('xl/sharedStrings.xml'))
            textos = [''.join(n.itertext()) for n in strings]
            sheet = ET.fromstring(arquivo.read('xl/worksheets/sheet1.xml'))
            ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            cabecalhos = {c.attrib['r'][:-1]: textos[int(c.find('x:v', ns).text)]
                          for c in sheet.findall('x:sheetData/x:row', ns)[0]}
            coluna = next(c for c, nome in cabecalhos.items() if nome == 'Tempo Produção Robô')
            valor = sheet.find(f'.//x:c[@r="{coluna}2"]/x:v', ns)
            assert abs(float(valor.text) - 30600 / 86400) < 1e-10
            assert 'Fim Produção Robô (Dia 4)' not in cabecalhos.values()
            coluna_velocidade = next(c for c, nome in cabecalhos.items() if nome == 'Velocidade Robô')
            velocidade = sheet.find(f'.//x:c[@r="{coluna_velocidade}2"]/x:v', ns)
            assert abs(float(velocidade.text) - 1000 / 510) < 1e-10

        # Desmarcar um dia no formulário apaga os dois horários e recalcula o total.
        form['inicio_prod_robo_4'] = form['fim_prod_robo_4'] = ''
        assert admin_client.post(f'/editar/{salvo["id"]}', data=form).status_code == 302
        conn = get_db_connection()
        try:
            editado = conn.execute('SELECT tempo_prod_robo, inicio_prod_robo_4 FROM producao WHERE id = ?', (salvo['id'],)).fetchone()
            assert editado['tempo_prod_robo'] == 27000
            assert not editado['inicio_prod_robo_4']
        finally:
            conn.close()
        for coluna in list(form):
            if coluna.startswith(('inicio_prod_robo', 'fim_prod_robo')):
                form[coluna] = ''
        assert admin_client.post(f'/editar/{salvo["id"]}', data=form).status_code == 302
        sem_horarios = admin_client.get('/historico', query_string={
            'num_of': num_of, 'sort_by': 'velocidade_un_min_robo',
        })
        assert sem_horarios.status_code == 200
        assert 'Velocidade Robô' in sem_horarios.get_data(as_text=True)
        assert '00:00:00' in sem_horarios.get_data(as_text=True)
    finally:
        conn = get_db_connection()
        conn.execute('DELETE FROM producao WHERE num_of = ?', (num_of,))
        conn.commit()
        conn.close()
