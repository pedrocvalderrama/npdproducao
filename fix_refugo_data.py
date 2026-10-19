from app.models import get_db_connection
import pandas as pd

conn = get_db_connection()

# Busca todos os registros onde refugo_flexo, refugo_pre_impresso e refugo_sos são 0
# mas refugo_pct > 0 (indicando que são dados antigos)
df = pd.read_sql_query("""
    SELECT id, refugo_pct, quantidade, milheiro, refugo_flexo, refugo_pre_impresso, refugo_sos, refugo
    FROM producao 
    WHERE refugo_flexo = 0 AND refugo_pre_impresso = 0 AND refugo_sos = 0 
    AND refugo_pct > 0
""", conn)

print(f'Encontrados {len(df)} registros para atualizar')

if not df.empty:
    cursor = conn.cursor()
    
    for idx, row in df.iterrows():
        # Calcula o refugo total a partir do refugo_pct existente
        peso_boas = row['quantidade'] * (row['milheiro'] / 1000)
        refugo_total = (row['refugo_pct'] / 100) * peso_boas
        
        # Distribui o refugo total entre as 3 colunas (assumindo distribuição igual)
        # Na prática, você pode ajustar essa distribuição conforme necessário
        refugo_flexo = refugo_total * 0.4  # 40% para flexo
        refugo_pre_impresso = refugo_total * 0.3  # 30% para pré-impresso  
        refugo_sos = refugo_total * 0.3  # 30% para SOS
        
        # Atualiza o registro
        cursor.execute("""
            UPDATE producao 
            SET refugo_flexo = ?, refugo_pre_impresso = ?, refugo_sos = ?, refugo = ?
            WHERE id = ?
        """, (refugo_flexo, refugo_pre_impresso, refugo_sos, refugo_total, row['id']))
        
        print(f'ID {row["id"]}: refugo_pct={row["refugo_pct"]:.2f}% -> refugo_total={refugo_total:.2f}kg')
    
    conn.commit()
    print(f'Atualizados {len(df)} registros com sucesso!')
else:
    print('Nenhum registro encontrado para atualizar')

conn.close()
