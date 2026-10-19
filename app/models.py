import sqlite3
from .config import DB_NAME

# Retorna uma conexão com o banco de dados SQLite
def get_db_connection():
    """Retorna uma conexão com o banco de dados SQLite."""
    # timeout maior evita "database is locked" quando há escrita concorrente;
    # WAL permite leituras simultâneas a uma escrita em andamento.
    conn = sqlite3.connect(DB_NAME, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

# Inicializa o banco de dados, criando a tabela 'producao' se não existir
def inicializar_banco():
    """Inicializa o banco de dados, criando a tabela 'producao' se ela não existir."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS producao (
            id INTEGER PRIMARY KEY AUTOINCREMENT, num_of TEXT, data TEXT, operador TEXT, maquina TEXT,
            qtd_cliches INTEGER, tipo TEXT, formato TEXT, papel TEXT, servico TEXT, milheiro REAL,
            refugo_flexo REAL, refugo_pre_impresso REAL, refugo_sos REAL, refugo_acerto_flexo REAL, 
            refugo_acerto_sos REAL, refugo REAL, quantidade INTEGER, inicio_prod TEXT, fim_prod TEXT, 
            inicio_prod_2 TEXT, fim_prod_2 TEXT, inicio_acerto TEXT, fim_acerto TEXT, observacoes TEXT, 
            refugo_pct REAL, eficiencia_pct REAL, velocidade_un_min REAL, perdas_un REAL, 
            tempo_prod_s INTEGER, tempo_acerto_s INTEGER
        )
    """)
    
    # Adiciona as novas colunas se elas não existirem (para compatibilidade com bancos existentes)
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN refugo_flexo REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN refugo_pre_impresso REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN refugo_sos REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN refugo_acerto_flexo REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN refugo_acerto_sos REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN tipo_impressao TEXT DEFAULT ''")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN consumo_util REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN consumo_total REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN quantidade_comanda INTEGER DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN numero_pedido INTEGER DEFAULT NULL")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN refugo_robo REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN refugo_inspecao_final REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN data_impressora TEXT DEFAULT NULL")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN data_inspecao TEXT DEFAULT NULL")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN quantidade_impressora INTEGER DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN quantidade_inspecao_geral INTEGER DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN inicio_acerto_impressora TEXT DEFAULT NULL")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN fim_acerto_impressora TEXT DEFAULT NULL")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN inicio_prod_impressora TEXT DEFAULT NULL")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN fim_prod_impressora TEXT DEFAULT NULL")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN tempo_acerto_impressora INTEGER DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN tempo_prod_impressora INTEGER DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN operador_impressora TEXT DEFAULT NULL")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN refugo_pct_flexo REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN velocidade_un_min_flexo REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN perdas_geral REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN perdas_geral_kg REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN data_robo TEXT DEFAULT NULL")
    except:
        pass  # Coluna já existe
    
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN quantidade_robo INTEGER DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    # Renomeia a coluna 'refugo' para 'refugo_producao_total' se ainda não foi renomeada
    try:
        cursor.execute("ALTER TABLE producao RENAME COLUMN refugo TO refugo_producao_total")
    except:
        pass  # Coluna já foi renomeada ou SQLite não suporta RENAME COLUMN (versão antiga)
    
    # Renomeia a coluna 'maquina' para 'sos' se ainda não foi renomeada
    try:
        cursor.execute("ALTER TABLE producao RENAME COLUMN maquina TO sos")
    except:
        pass  # Coluna já foi renomeada ou SQLite não suporta RENAME COLUMN (versão antiga)
    
    # Adiciona coluna 'impressora' se ainda não existe
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN impressora TEXT DEFAULT NULL")
    except:
        pass  # Coluna já existe
    
    # Adiciona coluna 'robo_alca' se ainda não existe
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN robo_alca TEXT DEFAULT NULL")
    except:
        pass  # Coluna já existe
    
    # Adiciona coluna 'operador_robo' se ainda não existe
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN operador_robo TEXT DEFAULT NULL")
    except:
        pass  # Coluna já existe
    
    # Adiciona coluna 'refugo_robo_kg' se ainda não existe
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN refugo_robo_kg REAL DEFAULT 0")
    except:
        pass  # Coluna já existe
    
    # Adiciona coluna 'refugo_inspecao_final_kg' se ainda não existe
    try:
        cursor.execute("ALTER TABLE producao ADD COLUMN refugo_inspecao_final_kg REAL DEFAULT 0")
    except:
        pass  # Coluna já existe

    for col in ('inicio_prod_3', 'fim_prod_3', 'inicio_prod_4', 'fim_prod_4'):
        try:
            cursor.execute(f"ALTER TABLE producao ADD COLUMN {col} TEXT DEFAULT NULL")
        except:
            pass  # Coluna já existe

    for col in ('inicio_prod_impressora_2', 'fim_prod_impressora_2', 'inicio_prod_impressora_3', 'fim_prod_impressora_3', 'inicio_prod_impressora_4', 'fim_prod_impressora_4'):
        try:
            cursor.execute(f"ALTER TABLE producao ADD COLUMN {col} TEXT DEFAULT NULL")
        except:
            pass  # Coluna já existe
    
    # Cria tabela de metas mensais se não existir
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metas_mensais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ano INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            meta_quantidade REAL NOT NULL,
            UNIQUE(ano, mes)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS formatos_cadastro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL UNIQUE,
            largura_bobina REAL NOT NULL,
            velocidade_ideal REAL NOT NULL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS formato_tolerancias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            formato_id INTEGER NOT NULL REFERENCES formatos_cadastro(id) ON DELETE CASCADE,
            papel TEXT NOT NULL,
            min_kg REAL NOT NULL,
            max_kg REAL NOT NULL,
            UNIQUE (formato_id, papel)
        )
    """)

    from .services.formato_migration import migrar_formatos_legados
    migrar_formatos_legados(conn)
    
    from .pedidos import inicializar_tabela_pedidos
    inicializar_tabela_pedidos(conn)

    # Índices para acelerar filtros e ordenação usados no Histórico, OF-Refugo,
    # Comparação e Pedidos (a tabela não tinha nenhum índice além do implícito).
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_producao_num_of ON producao(num_of)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_producao_data ON producao(data)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_producao_numero_pedido ON producao(numero_pedido)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_pedido ON pedidos(pedido)")

    conn.commit()
    conn.close() 