import csv
import os

from .custo.utils.formatters import formatar_data_iso
from .models import get_db_connection

PEDIDOS_CSV_NAME = 'sisplanpedidos.csv'

COLUMN_ORDER = [
    'condicao', 'pedido', 'fantasia', 'emissao', 'entrega', 'qtde_total',
    'medida', 'papel', 'grupo', 'preco', 'cidade', 'uf', 'obs',
    'valor_item', 'representante', 'responsavel', 'motivo',
]

COLUMN_LABELS = {
    'condicao': 'CONDICAO',
    'pedido': 'PEDIDO',
    'fantasia': 'FANTASIA',
    'emissao': 'EMISSAO',
    'entrega': 'ENTREGA',
    'qtde_total': 'QTDE_TOTAL',
    'medida': 'MEDIDA',
    'papel': 'PAPEL',
    'grupo': 'GRUPO',
    'preco': 'PRECO',
    'cidade': 'CIDADE',
    'uf': 'UF',
    'obs': 'OBS',
    'valor_item': 'VALOR ITEM',
    'representante': 'REPRESENTANTE',
    'responsavel': 'RESPONSAVEL',
    'motivo': 'MOTIVO',
}

DATE_COLUMNS = {'emissao', 'entrega'}
REAL_COLUMNS = {'preco', 'valor_item'}
INTEGER_COLUMNS = {'pedido', 'qtde_total'}

CSV_TO_DB = {
    'CONDICAO_ENTREGA': 'condicao',
    'CONDICAO': 'condicao',
    'PEDIDO': 'pedido',
    'FANTASIA': 'fantasia',
    'EMISSAO_PEDIDO': 'emissao',
    'EMISSAO': 'emissao',
    'ENTREGA_PEDIDO': 'entrega',
    'ENTREGA': 'entrega',
    'QTDE_TOTAL': 'qtde_total',
    'MEDIDA': 'medida',
    'PAPEL': 'papel',
    'GRUPO': 'grupo',
    'PRECO': 'preco',
    'CIDADE': 'cidade',
    'UF': 'uf',
    'OBS': 'obs',
    'VALOR_ITEM': 'valor_item',
    'VALOR ITEM': 'valor_item',
    'REPRESENTATE': 'representante',
    'REPRESENTANTE': 'representante',
    'RESPONSAVEL': 'responsavel',
    'MOTIVO': 'motivo',
}

GRUPO_EXCLUIDO = 'CLICHES'
CSV_ENCODINGS = ('utf-8-sig', 'cp1252', 'latin-1')


def _detect_csv_encoding(path):
    with open(path, 'rb') as csv_file:
        raw = csv_file.read()
    for encoding in CSV_ENCODINGS:
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return 'latin-1'


def _is_grupo_cliches(grupo):
    return _clean_text(grupo).upper() == GRUPO_EXCLUIDO


def get_csv_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, PEDIDOS_CSV_NAME)


def inicializar_tabela_pedidos(conn=None):
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    conn.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            condicao TEXT,
            pedido INTEGER,
            fantasia TEXT,
            emissao TEXT,
            entrega TEXT,
            qtde_total INTEGER,
            medida TEXT,
            papel TEXT,
            grupo TEXT,
            preco REAL,
            cidade TEXT,
            uf TEXT,
            obs TEXT,
            valor_item REAL,
            representante TEXT,
            responsavel TEXT,
            motivo TEXT,
            custo REAL
        )
    """)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(pedidos)").fetchall()]
    if 'custo' not in cols:
        conn.execute("ALTER TABLE pedidos ADD COLUMN custo REAL")
    conn.commit()
    if close_conn:
        conn.close()


def _clean_text(value):
    if value is None:
        return ''
    text = str(value).strip().strip('"')
    return text


def _parse_int(value):
    text = _clean_text(value)
    if not text:
        return None
    text = text.replace('.', '').replace(',', '')
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return None


def _parse_real(value):
    text = _clean_text(value)
    if not text:
        return None
    text = text.replace('.', '').replace(',', '.') if text.count(',') == 1 else text.replace(',', '.')
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def _parse_date(value):
    text = _clean_text(value)
    if not text:
        return None
    return formatar_data_iso(text)


def _normalize_row(raw_row):
    normalized = {col: None for col in COLUMN_ORDER}
    for csv_col, value in raw_row.items():
        db_col = CSV_TO_DB.get(_clean_text(csv_col).upper().replace('  ', ' '))
        if not db_col:
            continue
        if db_col in DATE_COLUMNS:
            normalized[db_col] = _parse_date(value)
        elif db_col in INTEGER_COLUMNS:
            normalized[db_col] = _parse_int(value)
        elif db_col in REAL_COLUMNS:
            normalized[db_col] = _parse_real(value)
        else:
            normalized[db_col] = _clean_text(value) or None
    return normalized


def _linha_ja_existe(cursor, row):
    """
    Verifica se já existe uma linha idêntica em `pedidos` (mesmos valores em
    todas as colunas do CSV). Evita duplicar a mesma linha quando o CSV é
    reimportado, sem impedir múltiplas linhas legítimas com o mesmo número de
    pedido (um pedido pode ter vários itens).
    """
    conditions = []
    values = []
    for col in COLUMN_ORDER:
        value = row.get(col)
        if value is None:
            conditions.append(f"{col} IS NULL")
        else:
            conditions.append(f"{col} = ?")
            values.append(value)
    query = f"SELECT 1 FROM pedidos WHERE {' AND '.join(conditions)} LIMIT 1"
    return cursor.execute(query, values).fetchone() is not None


def importar_pedidos_csv(csv_path=None):
    """Importa pedidos do CSV adicionando ao banco, sem remover dados existentes.

    Linhas idênticas a alguma já existente são ignoradas (deduplicação),
    evitando que reimportações repetidas do mesmo arquivo inflem a tabela.
    """
    path = csv_path or get_csv_path()
    if not os.path.isfile(path):
        raise FileNotFoundError(f'Arquivo não encontrado: {path}')

    conn = get_db_connection()
    inicializar_tabela_pedidos(conn)
    cursor = conn.cursor()

    inseridos = 0
    ignorados = 0
    duplicados = 0

    encoding = _detect_csv_encoding(path)

    with open(path, 'r', encoding=encoding, newline='') as csv_file:
        reader = csv.DictReader(csv_file, delimiter=';')
        for raw_row in reader:
            row = _normalize_row(raw_row)
            if _is_grupo_cliches(row.get('grupo')):
                ignorados += 1
                continue
            if row.get('pedido') is None:
                ignorados += 1
                continue
            if _linha_ja_existe(cursor, row):
                duplicados += 1
                continue

            columns = [col for col in COLUMN_ORDER if col in row]
            placeholders = ', '.join(['?'] * len(columns))
            col_names = ', '.join(columns)
            values = [row[col] for col in columns]
            cursor.execute(
                f"INSERT INTO pedidos ({col_names}) VALUES ({placeholders})",
                values,
            )
            inseridos += 1

    conn.commit()
    conn.close()
    return {'inseridos': inseridos, 'ignorados': ignorados, 'duplicados': duplicados}


def listar_pedidos(args, paginado=False, per_page=100):
    """
    Lista pedidos aplicando os filtros de `args`.

    Por padrão retorna a lista completa (usada internamente por outras telas,
    como o cálculo de custo do Movimento, que precisa do conjunto completo
    para localizar pedidos vizinhos). Quando `paginado=True`, retorna um dict
    com a página atual e metadados de paginação, evitando carregar milhares
    de linhas no HTML de uma vez.
    """
    conn = get_db_connection()
    inicializar_tabela_pedidos(conn)

    query = "SELECT * FROM pedidos WHERE 1=1"
    params = []

    pedido = args.get('pedido', '').strip()
    if pedido:
        query += " AND CAST(pedido AS TEXT) LIKE ?"
        params.append(f'%{pedido}%')

    fantasia = args.get('fantasia', '').strip()
    if fantasia:
        query += " AND fantasia LIKE ?"
        params.append(f'%{fantasia}%')

    cidade = args.get('cidade', '').strip()
    if cidade:
        query += " AND cidade LIKE ?"
        params.append(f'%{cidade}%')

    uf = args.get('uf', '').strip()
    if uf:
        query += " AND uf LIKE ?"
        params.append(f'%{uf}%')

    grupo = args.get('grupo', '').strip()
    if grupo:
        query += " AND grupo LIKE ?"
        params.append(f'%{grupo}%')

    representante = args.get('representante', '').strip()
    if representante:
        query += " AND representante LIKE ?"
        params.append(f'%{representante}%')

    start_emissao = args.get('start_emissao')
    end_emissao = args.get('end_emissao')
    if start_emissao and end_emissao:
        query += " AND emissao BETWEEN ? AND ?"
        params.extend([start_emissao, end_emissao])

    start_entrega = args.get('start_entrega')
    end_entrega = args.get('end_entrega')
    if start_entrega and end_entrega:
        query += " AND entrega BETWEEN ? AND ?"
        params.extend([start_entrega, end_entrega])

    sort_by = args.get('sort_by', 'pedido')
    sort_order = args.get('sort_order', 'desc')
    allowed_sort = ['id'] + COLUMN_ORDER
    if sort_by not in allowed_sort:
        sort_by = 'pedido'
    if sort_order not in ('asc', 'desc'):
        sort_order = 'desc'
    query_where = query
    query += f" ORDER BY {sort_by} {sort_order}"

    if not paginado:
        rows = conn.execute(query, tuple(params)).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    count_query = query_where.replace("SELECT * FROM pedidos", "SELECT COUNT(*) AS total FROM pedidos", 1)
    total_registros = conn.execute(count_query, tuple(params)).fetchone()['total']
    total_paginas = max(1, (total_registros + per_page - 1) // per_page)
    try:
        page = int(args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    page = max(1, min(page, total_paginas))
    offset = (page - 1) * per_page
    rows = conn.execute(query + " LIMIT ? OFFSET ?", tuple(params) + (per_page, offset)).fetchall()
    conn.close()
    return {
        'rows': [dict(row) for row in rows],
        'page': page,
        'total_paginas': total_paginas,
        'total_registros': total_registros,
        'per_page': per_page,
    }


def buscar_pedidos_por_numero(pedido):
    """Retorna linhas do pedido informado para lançamento de custo."""
    conn = get_db_connection()
    inicializar_tabela_pedidos(conn)

    pedido_int = _parse_int(pedido)
    if pedido_int is None:
        conn.close()
        return []

    rows = conn.execute(
        """
        SELECT id, pedido, fantasia, qtde_total, medida, papel, grupo, custo
        FROM pedidos
        WHERE pedido = ?
        ORDER BY id
        """,
        (pedido_int,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def lancar_custo_pedido(pedido_id, custo):
    """Grava custo manual na linha do pedido (exibido em /movimento)."""
    conn = get_db_connection()
    inicializar_tabela_pedidos(conn)
    try:
        custo_val = float(str(custo).replace(',', '.'))
    except (TypeError, ValueError):
        conn.close()
        return False

    cursor = conn.execute(
        "UPDATE pedidos SET custo = ? WHERE id = ?",
        (custo_val, int(pedido_id)),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def excluir_pedido(pedido_id):
    """Remove uma linha de pedido pelo ID."""
    conn = get_db_connection()
    inicializar_tabela_pedidos(conn)
    cursor = conn.execute("DELETE FROM pedidos WHERE id = ?", (int(pedido_id),))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted
