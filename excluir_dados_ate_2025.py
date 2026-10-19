"""
Script para excluir da tabela producao todos os registros em que a Data SOS
seja de 2025 ou anterior (ano <= 2025).

Execute na pasta do projeto: py excluir_dados_ate_2025.py
Ou: python excluir_dados_ate_2025.py
"""
import sys
import os

# Garante que o app está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import DB_NAME
import sqlite3

def main():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Conta quantos registros serao excluidos (Data SOS com ano <= 2025)
    # data no formato YYYY-MM-DD ou similar; ano = primeiros 4 caracteres
    cursor.execute("""
        SELECT COUNT(*) as total FROM producao
        WHERE data IS NOT NULL AND CAST(substr(data, 1, 4) AS INTEGER) <= 2025
    """)
    total = cursor.fetchone()[0]

    if total == 0:
        print("Nenhum registro com Data SOS em 2025 ou anterior encontrado. Nada a excluir.")
        conn.close()
        return

    print(f"Encontrados {total} registro(s) com Data SOS em 2025 ou anterior.")
    print("Deseja excluir? (digite SIM em maiusculas para confirmar): ", end="")
    resp = input().strip()
    if resp != "SIM":
        print("Operacao cancelada.")
        conn.close()
        return

    cursor.execute("""
        DELETE FROM producao
        WHERE data IS NOT NULL AND CAST(substr(data, 1, 4) AS INTEGER) <= 2025
    """)
    conn.commit()
    print(f"{cursor.rowcount} registro(s) excluido(s).")
    conn.close()

if __name__ == "__main__":
    main()
