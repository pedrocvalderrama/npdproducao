"""
Módulo de conexão com o banco de dados SQLite (compartilhado com produção e custos).

A lógica de conexão em si vive em app.models.get_db_connection (fonte única —
antes havia duas implementações idênticas, uma aqui e outra em app/models.py).
Este módulo permanece como ponto de entrada para o código de custos, que já
depende de `get_db`/`criar_tabelas_custo` importados daqui.
"""
from app.models import get_db_connection as get_db


def criar_tabelas_custo():
    """
    Cria as tabelas de custo (custo_papel, custo_operacional) se não existirem.
    """
    conn = None
    try:
        conn = get_db()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS custo_papel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                papel TEXT NOT NULL,
                custo_kg REAL NOT NULL,
                data_registro TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS custo_operacional (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                despesa TEXT NOT NULL,
                custo_unidade REAL NOT NULL,
                data_registro TEXT NOT NULL
            )
        """)

        conn.commit()
    except Exception as e:
        print(f"Aviso na criação de tabelas de custo: {e}")
    finally:
        if conn:
            conn.close()
