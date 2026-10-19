"""Rotas de Pedidos (CSV Sisplan) e Movimento (custo por pedido)."""
from flask import render_template, request, flash, send_file, redirect, url_for, session, jsonify
from datetime import datetime
import pandas as pd
from io import BytesIO
from ..models import get_db_connection, inicializar_banco
from ..business import calcular_metricas_producao, calc_tempo_producao_impressora, enrich_lancamento_observacoes, get_seconds_from_time, observacoes_from_form
from ..config import ALL_OPERADORES, ALL_MAQUINAS, MAQUINAS_SOS, OPERADORES_SOS, OPERADORES_IMPRESSORA, OPERADORES_ROBO
from ..utils import safe_get_int, safe_get_float, safe_get_str
from . import main_bp

# Rota para exibir pedidos importados do CSV Sisplan
@main_bp.route("/pedidos")
def pedidos():
    from ..pedidos import COLUMN_LABELS, COLUMN_ORDER, DATE_COLUMNS, INTEGER_COLUMNS, REAL_COLUMNS, listar_pedidos

    args = request.args.copy()
    preserved_args = args.copy()
    preserved_args.pop('sort_by', None)
    preserved_args.pop('sort_order', None)
    preserved_args.pop('page', None)

    if args.get("export") == "excel":
        pedidos_list = listar_pedidos(args)
        try:
            if pedidos_list:
                df_data = []
                for item in pedidos_list:
                    row = {COLUMN_LABELS[col]: item.get(col) for col in COLUMN_ORDER if col in item}
                    df_data.append(row)
                df = pd.DataFrame(df_data)
                for col in [COLUMN_LABELS[c] for c in DATE_COLUMNS]:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                for col in [COLUMN_LABELS[c] for c in REAL_COLUMNS]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
            else:
                df = pd.DataFrame()

            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Pedidos')
                if not df.empty:
                    workbook = writer.book
                    ws = writer.sheets['Pedidos']
                    fmt_number = workbook.add_format({'num_format': '#,##0.00'})
                    fmt_date = workbook.add_format({'num_format': 'dd/mm/yyyy'})
                    for i, col in enumerate(df.columns):
                        width = max(int(df[col].astype(str).str.len().max()), len(col)) + 2
                        if col in [COLUMN_LABELS[c] for c in DATE_COLUMNS]:
                            ws.set_column(i, i, width, fmt_date)
                        elif col in [COLUMN_LABELS[c] for c in REAL_COLUMNS]:
                            ws.set_column(i, i, width, fmt_number)
                        else:
                            ws.set_column(i, i, width)
            output.seek(0)
            return send_file(output, download_name="pedidos.xlsx", as_attachment=True)
        except Exception as e:
            flash(f"Erro ao exportar: {e}", "danger")
            return redirect(url_for('main.pedidos'))

    pagination_args = args.copy()
    pagination_args.pop('page', None)
    resultado = listar_pedidos(args, paginado=True)

    contexto = dict(
        pedidos=resultado['rows'],
        column_order=COLUMN_ORDER,
        column_labels=COLUMN_LABELS,
        date_columns=DATE_COLUMNS,
        real_columns=REAL_COLUMNS,
        integer_columns=INTEGER_COLUMNS,
        preserved_args=preserved_args,
        pagination_args=pagination_args,
        action_url=url_for('main.pedidos'),
        page=resultado['page'],
        total_paginas=resultado['total_paginas'],
        total_registros=resultado['total_registros'],
        per_page=resultado['per_page'],
    )
    if request.headers.get('HX-Request') == 'true':
        return render_template('partials/pedidos_resultado.html', **contexto)
    return render_template('pedidos.html', **contexto)


@main_bp.route("/pedidos/atualizar", methods=["POST"])
def atualizar_pedidos():
    from ..pedidos import importar_pedidos_csv

    try:
        resultado = importar_pedidos_csv()
        flash(
            f"AtualizaÃ§Ã£o concluÃ­da: {resultado['inseridos']} pedido(s) adicionado(s), "
            f"{resultado['ignorados']} linha(s) ignorada(s) (invÃ¡lidas ou grupo CLICHES), "
            f"{resultado['duplicados']} linha(s) jÃ¡ existente(s) ignorada(s).",
            "success",
        )
    except FileNotFoundError as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"Erro ao importar pedidos: {e}", "danger")
    return redirect(url_for('main.pedidos'))


@main_bp.route("/pedidos/excluir/<int:id>", methods=["POST"])
def excluir_pedido_route(id):
    from ..pedidos import excluir_pedido

    try:
        if excluir_pedido(id):
            flash("Registro excluÃ­do com sucesso.", "success")
        else:
            flash("Registro nÃ£o encontrado.", "warning")
    except Exception as e:
        flash(f"Erro ao excluir registro: {e}", "danger")

    referrer = request.referrer
    if referrer:
        return redirect(referrer)
    return redirect(url_for('main.pedidos'))


# Rota para exibir movimento (pedidos + coluna custo calculada)
@main_bp.route("/movimento")
def movimento():
    from ..movimento import (
        MOVIMENTO_COLUMN_LABELS,
        MOVIMENTO_COLUMN_ORDER,
        MOVIMENTO_REAL_COLUMNS,
        listar_movimento,
    )
    from ..pedidos import DATE_COLUMNS, INTEGER_COLUMNS

    args = request.args.copy()
    movimento_list = listar_movimento(args)
    preserved_args = args.copy()
    preserved_args.pop('sort_by', None)
    preserved_args.pop('sort_order', None)
    preserved_args.pop('page', None)

    if args.get("export") == "excel":
        try:
            if movimento_list:
                df_data = []
                for item in movimento_list:
                    row = {
                        MOVIMENTO_COLUMN_LABELS[col]: item.get(col)
                        for col in MOVIMENTO_COLUMN_ORDER
                        if col in item
                    }
                    df_data.append(row)
                df = pd.DataFrame(df_data)
                for col in [MOVIMENTO_COLUMN_LABELS[c] for c in DATE_COLUMNS]:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                for col in [MOVIMENTO_COLUMN_LABELS[c] for c in MOVIMENTO_REAL_COLUMNS]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
            else:
                df = pd.DataFrame()

            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Movimento')
                if not df.empty:
                    workbook = writer.book
                    ws = writer.sheets['Movimento']
                    fmt_number = workbook.add_format({'num_format': '#,##0.00'})
                    fmt_date = workbook.add_format({'num_format': 'dd/mm/yyyy'})
                    for i, col in enumerate(df.columns):
                        width = max(int(df[col].astype(str).str.len().max()), len(col)) + 2
                        if col in [MOVIMENTO_COLUMN_LABELS[c] for c in DATE_COLUMNS]:
                            ws.set_column(i, i, width, fmt_date)
                        elif col in [MOVIMENTO_COLUMN_LABELS[c] for c in MOVIMENTO_REAL_COLUMNS]:
                            ws.set_column(i, i, width, fmt_number)
                        else:
                            ws.set_column(i, i, width)
            output.seek(0)
            return send_file(output, download_name="movimento.xlsx", as_attachment=True)
        except Exception as e:
            flash(f"Erro ao exportar: {e}", "danger")
            return redirect(url_for('main.movimento'))

    # O cÃ¡lculo de custo depende do conjunto completo filtrado (busca pedidos
    # vizinhos), entÃ£o a paginaÃ§Ã£o aqui Ã© feita sÃ³ na exibiÃ§Ã£o, apÃ³s o cÃ¡lculo.
    pagination_args = args.copy()
    pagination_args.pop('page', None)
    per_page = 100
    total_registros = len(movimento_list)
    total_paginas = max(1, (total_registros + per_page - 1) // per_page)
    try:
        page = int(args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    page = max(1, min(page, total_paginas))
    offset = (page - 1) * per_page
    movimentos_pagina = movimento_list[offset:offset + per_page]

    contexto = dict(
        movimentos=movimentos_pagina,
        column_order=MOVIMENTO_COLUMN_ORDER,
        column_labels=MOVIMENTO_COLUMN_LABELS,
        date_columns=DATE_COLUMNS,
        real_columns=MOVIMENTO_REAL_COLUMNS,
        integer_columns=INTEGER_COLUMNS,
        preserved_args=preserved_args,
        pagination_args=pagination_args,
        action_url=url_for('main.movimento'),
        page=page,
        total_paginas=total_paginas,
        total_registros=total_registros,
        per_page=per_page,
    )
    if request.headers.get('HX-Request') == 'true':
        return render_template('partials/movimento_resultado.html', **contexto)
    return render_template('movimento.html', **contexto)


@main_bp.route("/movimento/atualizar", methods=["POST"])
def atualizar_movimento():
    from ..pedidos import importar_pedidos_csv

    try:
        resultado = importar_pedidos_csv()
        flash(
            f"AtualizaÃ§Ã£o concluÃ­da: {resultado['inseridos']} pedido(s) adicionado(s), "
            f"{resultado['ignorados']} linha(s) ignorada(s) (invÃ¡lidas ou grupo CLICHES), "
            f"{resultado['duplicados']} linha(s) jÃ¡ existente(s) ignorada(s).",
            "success",
        )
    except FileNotFoundError as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"Erro ao importar pedidos: {e}", "danger")
    return redirect(url_for('main.movimento'))

# Rota OF-Refugo (histÃ³rico simplificado)
