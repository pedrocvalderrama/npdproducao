"""
API JSON somente leitura (Fase 4 da auditoria de otimização).

Objetivo: permitir que sistemas externos (BI, automações, outro software da
fábrica) leiam os dados de produção/pedidos/custos sem precisar simular um
login por formulário HTML. Todas as rotas aqui são GET e somente leitura —
nenhuma delas faz INSERT/UPDATE/DELETE, então não há risco de um cliente
externo corromper dados.

Autenticação: header `X-API-Key` (ver `app/api_auth.py`) OU sessão de login
normal (para poder testar as rotas direto do navegador já autenticado).

Paginação: todas as listagens aceitam `?page=` (padrão 1) e `?per_page=`
(padrão 100, máximo 500) e devolvem um envelope padrão:

    {"data": [...], "page": 1, "per_page": 100, "total": 1234, "total_paginas": 13}

Todas as rotas estão documentadas também em `GET /api/v1/` (índice
autoexplicativo) e no README.md.
"""
from flask import Blueprint, jsonify, request, url_for

from ..models import get_db_connection
from ..pedidos import listar_pedidos as _listar_pedidos_service
from ..movimento import listar_movimento as _listar_movimento_service

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

MAX_PER_PAGE = 500
DEFAULT_PER_PAGE = 100


def _paginacao_args():
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get('per_page', DEFAULT_PER_PAGE))
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE
    per_page = max(1, min(per_page, MAX_PER_PAGE))
    return page, per_page


def _listar_paginado(conn, tabela, colunas_filtro=None, filtros_like=None, order_by='id DESC'):
    """
    Monta e executa uma listagem paginada de `tabela` com filtros simples de
    igualdade (colunas_filtro) e "contém" (filtros_like), devolvendo o
    envelope padrão de paginação.
    """
    where = []
    params = []
    for coluna in (colunas_filtro or []):
        valor = request.args.get(coluna)
        if valor:
            where.append(f"{coluna} = ?")
            params.append(valor)
    for coluna in (filtros_like or []):
        valor = request.args.get(coluna)
        if valor:
            where.append(f"{coluna} LIKE ?")
            params.append(f"%{valor}%")

    where_sql = f" WHERE {' AND '.join(where)}" if where else ""
    page, per_page = _paginacao_args()

    total = conn.execute(f"SELECT COUNT(*) AS n FROM {tabela}{where_sql}", params).fetchone()['n']
    total_paginas = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_paginas)
    offset = (page - 1) * per_page

    rows = conn.execute(
        f"SELECT * FROM {tabela}{where_sql} ORDER BY {order_by} LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    return jsonify({
        'data': [dict(r) for r in rows],
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_paginas': total_paginas,
    })


@api_bp.route('/')
def indice():
    """Índice autoexplicativo com todas as rotas disponíveis na API."""
    return jsonify({
        'versao': 'v1',
        'autenticacao': 'Header "X-API-Key: <chave>" (admin gera/consulta em /admin/api-key) ou sessão de login normal.',
        'paginacao': 'Parâmetros ?page= e ?per_page= (máx. 500) em todas as listagens; resposta no formato {data, page, per_page, total, total_paginas}.',
        'endpoints': [
            {'metodo': 'GET', 'rota': url_for('api.listar_producao'), 'descricao': 'Lista lançamentos de produção. Filtros: ?num_of=, ?servico= (contém), ?operador=, ?data= (AAAA-MM-DD).'},
            {'metodo': 'GET', 'rota': '/api/v1/producao/<id>', 'descricao': 'Um lançamento de produção específico pelo id.'},
            {'metodo': 'GET', 'rota': url_for('api.listar_pedidos'), 'descricao': 'Lista pedidos importados (CSV Sisplan). Filtros: ?pedido=, ?fantasia=, ?cidade=, ?uf=, ?grupo= (contém).'},
            {'metodo': 'GET', 'rota': url_for('api.listar_movimento'), 'descricao': 'Lista pedidos com custo/margem calculados (mesmos filtros de /pedidos).'},
            {'metodo': 'GET', 'rota': url_for('api.listar_custos_papel'), 'descricao': 'Lista o custo por kg cadastrado para cada tipo de papel.'},
            {'metodo': 'GET', 'rota': url_for('api.listar_custos_operacionais'), 'descricao': 'Lista as despesas operacionais cadastradas.'},
            {'metodo': 'GET', 'rota': url_for('api.resumo_mensal'), 'descricao': 'Resumo de quantidade produzida e % de refugo por mês. Parâmetro: ?ano= (padrão: ano atual).'},
        ],
    })


@api_bp.route('/producao')
def listar_producao():
    conn = get_db_connection()
    try:
        return _listar_paginado(
            conn, 'producao',
            colunas_filtro=['num_of', 'operador', 'data'],
            filtros_like=['servico'],
        )
    finally:
        conn.close()


@api_bp.route('/producao/<int:registro_id>')
def obter_producao(registro_id):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM producao WHERE id = ?", (registro_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return jsonify({'erro': 'Registro não encontrado.'}), 404
    return jsonify(dict(row))


@api_bp.route('/pedidos')
def listar_pedidos():
    """Reaproveita a mesma função de listagem/filtros usada pela tela HTML
    de Pedidos (`app/pedidos.py`), para não duplicar a lógica de filtros."""
    page, per_page = _paginacao_args()
    args = request.args.copy()
    args['page'] = str(page)
    resultado = _listar_pedidos_service(args, paginado=True, per_page=per_page)
    return jsonify({
        'data': resultado['rows'],
        'page': resultado['page'],
        'per_page': resultado['per_page'],
        'total': resultado['total_registros'],
        'total_paginas': resultado['total_paginas'],
    })


@api_bp.route('/movimento')
def listar_movimento():
    """Reaproveita `listar_movimento` (pedidos + custo/margem calculados),
    a mesma lógica usada pela tela HTML de Movimento. Como o cálculo de
    custo depende do conjunto completo de pedidos, a paginação é aplicada
    aqui, depois da lista já calculada."""
    page, per_page = _paginacao_args()
    linhas = _listar_movimento_service(request.args)
    total = len(linhas)
    total_paginas = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_paginas)
    inicio = (page - 1) * per_page
    return jsonify({
        'data': linhas[inicio:inicio + per_page],
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_paginas': total_paginas,
    })


@api_bp.route('/custos/papel')
def listar_custos_papel():
    conn = get_db_connection()
    try:
        return _listar_paginado(conn, 'custo_papel', order_by='papel ASC')
    finally:
        conn.close()


@api_bp.route('/custos/operacionais')
def listar_custos_operacionais():
    conn = get_db_connection()
    try:
        return _listar_paginado(conn, 'custo_operacional', order_by='despesa ASC')
    finally:
        conn.close()


@api_bp.route('/resumo-mensal')
def resumo_mensal():
    """
    Totais simples de quantidade produzida e % média de refugo por mês, para
    o ano informado (ou o ano atual). É um resumo independente e mais
    simples que o relatório completo da tela Comparativo Mensal (que soma
    metas, papel, bobina etc.) — pensado para consumo programático rápido.
    """
    from datetime import datetime
    ano = request.args.get('ano', str(datetime.now().year))

    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                CAST(strftime('%m', data) AS INTEGER) AS mes,
                COALESCE(SUM(quantidade), 0) AS quantidade_total,
                COALESCE(SUM(refugo_producao_total), 0) AS refugo_total_kg,
                COUNT(*) AS num_lancamentos
            FROM producao
            WHERE strftime('%Y', data) = ?
            GROUP BY mes
            ORDER BY mes
            """,
            (ano,),
        ).fetchall()
    finally:
        conn.close()

    return jsonify({
        'ano': ano,
        'meses': [dict(r) for r in rows],
    })
