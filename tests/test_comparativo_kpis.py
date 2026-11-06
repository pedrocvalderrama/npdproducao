import sqlite3

import pytest

from app.routes.analise import _calcular_kpis_mensais


def test_kpis_mes_fontes_datas_e_exclusao_resmadeira():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript('''
        CREATE TABLE lancamento_diario (data TEXT, equipamento TEXT, quantidade INTEGER);
        ALTER TABLE lancamento_diario ADD COLUMN refugo_diario INTEGER;
        CREATE TABLE metas_lancamento_diario (ano INTEGER, mes INTEGER, grupo TEXT, meta_quantidade REAL);
        CREATE TABLE producao (
            data TEXT, data_impressora TEXT, sos TEXT, impressora TEXT,
            quantidade REAL, quantidade_impressora REAL, milheiro REAL,
            velocidade_un_min REAL, velocidade_un_min_flexo REAL,
            refugo_acerto_sos REAL, refugo_pre_impresso REAL, refugo_sos REAL,
            refugo_flexo REAL, refugo_acerto_flexo REAL, refugo_pct REAL, refugo_pct_flexo REAL
        );
        INSERT INTO lancamento_diario (data, equipamento, quantidade) VALUES
            ('2026-09-05', 'SOS 1', 1000), ('2026-09-30', 'SOS 2', 500),
            ('2026-10-01', 'SOS 1', 99999), ('2025-09-01', 'SOS 1', 99999),
            ('2026-09-01', 'RESMADEIRA', 99999),
            ('2026-09-01', 'IMPRESSORA', 800), ('2026-09-01', 'ROBO', 300);
        INSERT INTO metas_lancamento_diario VALUES
            (2026, 9, 'SOS', 2000), (2026, 9, 'IMPRESSORA', 0);
        INSERT INTO producao VALUES
            ('2026-09-01', '2026-10-01', 'SOS 1', 'IMPRESSORA',
             1000, 800, 10, 100, 999, 1, 1, 2, 2, 1, 0, 0),
            ('2026-09-02', '2026-09-01', 'SOS 2', 'IMPRESSORA',
             2000, 1000, 10, 200, 50, 1, 1, 2, 2, 1, 0, 0),
            ('2026-09-03', NULL, 'RESMADEIRA', NULL,
             99999, 0, 10, 999, 0, 100, 100, 100, 0, 0, 0, 0);
        ALTER TABLE producao ADD COLUMN data_robo TEXT;
        ALTER TABLE producao ADD COLUMN robo_alca TEXT;
        ALTER TABLE producao ADD COLUMN refugo_robo REAL;
        ALTER TABLE producao ADD COLUMN inicio_prod TEXT;
        ALTER TABLE producao ADD COLUMN fim_prod TEXT;
        ALTER TABLE producao ADD COLUMN inicio_prod_2 TEXT;
        ALTER TABLE producao ADD COLUMN fim_prod_2 TEXT;
        ALTER TABLE producao ADD COLUMN inicio_prod_impressora TEXT;
        ALTER TABLE producao ADD COLUMN fim_prod_impressora TEXT;
        ALTER TABLE producao ADD COLUMN inicio_prod_impressora_2 TEXT;
        ALTER TABLE producao ADD COLUMN fim_prod_impressora_2 TEXT;
        UPDATE producao SET inicio_prod = '08:00', fim_prod = '10:30',
            inicio_prod_2 = '23:00', fim_prod_2 = '01:00',
            inicio_prod_impressora = '09:00', fim_prod_impressora = '12:00',
            inicio_prod_impressora_2 = '13:00', fim_prod_impressora_2 = '14:30';
    ''')
    try:
        sos, impressora, robo = _calcular_kpis_mensais(conn, 2026, 9)
        assert sos['producao'] == 1500  # Inclui sábado do Histórico Diário.
        assert sos['atingimento'] == 75
        assert sos['produtividade'] == 150
        assert sos['horas'] == 9
        assert sos['refugo'] == pytest.approx(8 / 38 * 100)
        assert impressora['producao'] == 800
        assert impressora['atingimento'] is None
        assert impressora['produtividade'] == 50
        assert impressora['horas'] == 4.5
        assert impressora['refugo'] == pytest.approx(4 / 14 * 100)
        assert robo['producao'] == 300
        assert robo['produtividade'] == pytest.approx(300 / 9)
        assert robo['horas'] == 9
        assert robo['atingimento'] is None
        assert robo['refugo'] == 0
        conn.executescript('''
            UPDATE lancamento_diario SET refugo_diario = 20 WHERE equipamento = 'ROBO';
            INSERT INTO lancamento_diario (data, equipamento, quantidade) VALUES
                ('2026-09-01', 'ROBO', 100), ('2026-09-02', 'ROBO', 400),
                ('2026-09-03', 'ROBO', 0), ('2026-10-01', 'ROBO', 99999);
            UPDATE lancamento_diario SET refugo_diario = 80 WHERE equipamento = 'ROBO' AND data = '2026-09-03';
            INSERT INTO lancamento_diario VALUES ('2025-09-01', 'ROBO', 900, 99999);
            UPDATE lancamento_diario SET refugo_diario = 99999 WHERE equipamento = 'IMPRESSORA';
            INSERT INTO producao (data_robo, robo_alca, refugo_robo) VALUES
                ('2026-09-01', 'APLA-2R', 30),
                ('2026-09-30', 'APLA-2R', 70),
                ('2026-10-01', 'APLA-2R', 99999),
                ('2025-09-01', 'APLA-2R', 99999),
                ('2026-09-01', NULL, 99999),
                ('2026-09-01', '   ', 99999),
                (NULL, 'APLA-2R', 99999);
        ''')
        assert _calcular_kpis_mensais(conn, 2026, 9)[2]['produtividade'] == pytest.approx(800 / 18)
        assert _calcular_kpis_mensais(conn, 2026, 9)[2]['horas'] == 18
        assert _calcular_kpis_mensais(conn, 2026, 12)[2]['horas'] == 0
        assert _calcular_kpis_mensais(conn, 2026, 9)[2]['refugo'] == pytest.approx(100 / 900 * 100)
        assert _calcular_kpis_mensais(conn, 2026, 12)[2]['refugo'] is None
        assert _calcular_kpis_mensais(conn, 2026, 12)[2]['produtividade'] is None
        assert _calcular_kpis_mensais(conn, 2026, 12)[0]['producao'] == 0
    finally:
        conn.close()


def test_pagina_kpis_filtro_e_formulas(admin_client):
    response = admin_client.get('/comparativo-mensal?ano=2026&mes_kpi=9')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    kpis = html.split('<h3 id="kpis">')[1].split('<h3>Consumo de Papel por Bobina')[0]
    assert 'value="9" selected' in kpis
    assert 'Fórmulas dos KPI' in kpis
    assert 'Eficiência' not in kpis
    assert admin_client.get('/comparativo-mensal?ano=2026&mes_kpi=13').status_code == 200
