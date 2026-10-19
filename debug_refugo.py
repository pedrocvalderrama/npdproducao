from app.models import get_db_connection
import pandas as pd

conn = get_db_connection()
df = pd.read_sql_query('SELECT * FROM producao LIMIT 5', conn)
print('Dados do banco:')
print(df[['id', 'refugo_flexo', 'refugo_pre_impresso', 'refugo_sos', 'refugo', 'refugo_pct', 'quantidade', 'milheiro']].to_string())

print('\nVerificação de cálculo:')
if not df.empty:
    for idx, row in df.iterrows():
        refugo_calculado = row['refugo_flexo'] + row['refugo_pre_impresso'] + row['refugo_sos']
        peso_boas = row['quantidade'] * (row['milheiro'] / 1000)
        refugo_pct_calculado = (refugo_calculado / peso_boas) * 100 if peso_boas > 0 else 0
        print(f'ID {row["id"]}: refugo_calculado={refugo_calculado}, refugo_salvo={row["refugo"]}, refugo_pct_salvo={row["refugo_pct"]:.2f}%, refugo_pct_calculado={refugo_pct_calculado:.2f}%')

# Verificar totais para análise
print('\nTotais para análise:')
refugo_total = df['refugo'].sum()
peso_boas_total = (df['quantidade'] * (df['milheiro'] / 1000)).sum()
refugo_pct_total = (refugo_total / peso_boas_total) * 100 if peso_boas_total > 0 else 0
print(f'Refugo total: {refugo_total}')
print(f'Peso boas total: {peso_boas_total}')
print(f'Refugo % total: {refugo_pct_total:.2f}%')

conn.close()
