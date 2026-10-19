from collections import defaultdict

from app.custo.services.relatorio_service import obter_dados_relatorio
from app.pedidos import (
    COLUMN_LABELS,
    COLUMN_ORDER,
    DATE_COLUMNS,
    INTEGER_COLUMNS,
    REAL_COLUMNS,
    _clean_text,
    listar_pedidos,
)

MOVIMENTO_COLUMN_ORDER = [
    'pedido', 'fantasia', 'emissao', 'valor_item', 'qtde_total',
    'custo', 'margem', 'medida', 'grupo', 'entrega', 'papel',
    'cidade', 'responsavel',
]
MOVIMENTO_COLUMN_LABELS = {
    **{k: COLUMN_LABELS[k] for k in MOVIMENTO_COLUMN_ORDER if k in COLUMN_LABELS},
    'custo': 'CUSTO',
    'margem': 'MARGEM',
}
# Apenas colunas reais que de fato aparecem no Movimento (ex.: 'preco' não faz
# parte de MOVIMENTO_COLUMN_ORDER e quebrava a exportação Excel com KeyError)
MOVIMENTO_REAL_COLUMNS = (REAL_COLUMNS | {'custo', 'margem'}) & set(MOVIMENTO_COLUMN_ORDER)
PEDIDO_RANGE = 10
QTDE_TOLERANCIA = 0.20

GRUPO_MAP = {
    'SACOLAS PERSONALIZADAS': 'SACOLA',
    'SACOLAS PADRONIZADAS': 'SACOLA',
    'CARTUCHOS PERSONALIZADOS': 'CARTUCHO',
    'CARTUCHOS LISOS': 'CARTUCHO',
    'CARTUCHOS PADRONIZADOS': 'CARTUCHO',
}


def _norm_cmp(value):
    return _clean_text(value).upper()


def _norm_medida(value):
    return _norm_cmp(value)


def _norm_grupo(value):
    grupo = _norm_cmp(value)
    return GRUPO_MAP.get(grupo, grupo)


def _match_key(row):
    return (
        _norm_grupo(row.get('grupo')),
        _norm_medida(row.get('medida')),
        _norm_cmp(row.get('fantasia')),
    )


def _custo_key(pedido, medida):
    if pedido is None or not _norm_medida(medida):
        return None
    return (int(pedido), _norm_medida(medida))


def _build_custo_por_pedido():
    dados, _ = obter_dados_relatorio()
    index = {}
    for item in dados:
        pedido = item.get('numero_pedido')
        if pedido is None or pedido == '':
            continue
        try:
            pedido_int = int(pedido)
        except (TypeError, ValueError):
            continue

        formato = _norm_medida(item.get('formato'))
        if not formato:
            continue

        key = (pedido_int, formato)
        if key in index:
            continue

        quantidade = int(item.get('quantidade') or 0)
        custo_final = float(item.get('custo_final') or 0)
        if quantidade <= 0:
            continue

        index[key] = {
            'qtde': quantidade,
            'custo_final': custo_final,
            'coeficiente': custo_final / quantidade,
        }
    return index


def _buscar_custo_entrada(row, custo_index):
    key = _custo_key(row.get('pedido'), row.get('medida'))
    if not key:
        return None
    return custo_index.get(key)


def _buscar_custo_referencia(row, custo_index, group_index):
    custo_info = _buscar_custo_entrada(row, custo_index)
    if custo_info:
        return custo_info

    pedido = int(row['pedido'])
    key = _match_key(row)
    vizinhos = sorted(
        [
            candidate
            for candidate in group_index.get(key, [])
            if abs(int(candidate['pedido']) - pedido) <= PEDIDO_RANGE
        ],
        key=lambda candidate: abs(int(candidate['pedido']) - pedido),
    )

    for vizinho in vizinhos:
        custo_info = _buscar_custo_entrada(vizinho, custo_index)
        if custo_info:
            return custo_info

    return None


def _build_group_index(rows):
    index = defaultdict(list)
    for row in rows:
        if row.get('pedido') is None:
            continue
        index[_match_key(row)].append(row)
    return index


def _dentro_tolerancia(soma, qtde_ref):
    if qtde_ref <= 0:
        return True
    return abs(soma - qtde_ref) / qtde_ref <= QTDE_TOLERANCIA


def _selecionar_pedidos_acumulados(candidatos, qtde_ref):
    candidatos_ordenados = sorted(candidatos, key=lambda row: int(row['pedido']))
    selecionados = []
    soma = 0

    for row in candidatos_ordenados:
        selecionados.append(row)
        soma += int(row.get('qtde_total') or 0)
        if soma >= qtde_ref or _dentro_tolerancia(soma, qtde_ref):
            break

    return selecionados


def _candidatos_proximos(row, group_index):
    pedido = int(row['pedido'])
    key = _match_key(row)
    return [
        candidate
        for candidate in group_index.get(key, [])
        if abs(int(candidate['pedido']) - pedido) <= PEDIDO_RANGE
    ]


def _calcular_custo_linha(row, custo_index, group_index):
    if row.get('pedido') is None:
        return None

    custo_info = _buscar_custo_referencia(row, custo_index, group_index)
    if not custo_info:
        return None

    candidatos = _candidatos_proximos(row, group_index)
    if not candidatos:
        return None

    selecionados = _selecionar_pedidos_acumulados(candidatos, custo_info['qtde'])
    selecionados_ids = {item['id'] for item in selecionados}

    if row['id'] not in selecionados_ids:
        return None

    qtde_total = int(row.get('qtde_total') or 0)
    return custo_info['coeficiente'] * qtde_total


def aplicar_custos_movimento(rows, all_rows=None):
    base_rows = all_rows if all_rows is not None else rows
    custo_index = _build_custo_por_pedido()
    group_index = _build_group_index(base_rows)

    for row in rows:
        custo_manual = row.get('custo')
        if custo_manual is not None:
            row['custo'] = float(custo_manual)
        else:
            row['custo'] = _calcular_custo_linha(row, custo_index, group_index)
        row['margem'] = None

    return rows


def listar_movimento(args):
    sort_by = args.get('sort_by', 'pedido')
    sort_order = args.get('sort_order', 'desc')

    if sort_by == 'custo':
        args_sem_sort = args.copy()
        args_sem_sort.pop('sort_by', None)
        args_sem_sort.pop('sort_order', None)
        rows = listar_pedidos(args_sem_sort)
    else:
        rows = listar_pedidos(args)

    all_rows = listar_pedidos({})
    rows = aplicar_custos_movimento(rows, all_rows)

    if sort_by == 'custo':
        reverse = sort_order != 'asc'
        rows.sort(
            key=lambda row: (row.get('custo') is None, row.get('custo') if row.get('custo') is not None else 0),
            reverse=reverse,
        )

    return rows
