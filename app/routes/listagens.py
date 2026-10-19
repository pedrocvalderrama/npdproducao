"""Rotas de listagem/relatÃ³rio: OF-Refugo e ComparaÃ§Ã£o de Quantidade."""
from flask import render_template, request, flash, send_file, redirect, url_for, session, jsonify
from datetime import datetime
import pandas as pd
from io import BytesIO
from ..models import get_db_connection, inicializar_banco
from ..business import calcular_metricas_producao, calc_tempo_producao_impressora, enrich_lancamento_observacoes, get_seconds_from_time, observacoes_from_form
from ..config import ALL_OPERADORES, ALL_MAQUINAS, MAQUINAS_SOS, OPERADORES_SOS, OPERADORES_IMPRESSORA, OPERADORES_ROBO
from ..utils import safe_get_int, safe_get_float, safe_get_str
from . import main_bp

@main_bp.route("/of-refugo")
def of_refugo():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM producao", conn)
    conn.close()
    
    lancamentos = []
    
    if not df.empty:
        # Aplicar filtros
        servico = request.args.get('servico', '').strip()
        if servico:
            df = df[df['servico'].str.contains(servico, case=False, na=False)]
        num_of = request.args.get('num_of', '').strip()
        if num_of:
            df = df[df['num_of'].str.contains(num_of, case=False, na=False)]
        numero_pedido = request.args.get('numero_pedido', '').strip()
        if numero_pedido and 'numero_pedido' in df.columns:
            df = df[df['numero_pedido'].astype(str).str.contains(numero_pedido, case=False, na=False)]
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if start_date and end_date:
            df = df[(df['data'] >= start_date) & (df['data'] <= end_date)]
        start_date_impressora = request.args.get('start_date_impressora')
        end_date_impressora = request.args.get('end_date_impressora')
        if start_date_impressora and end_date_impressora:
            df = df[(df['data_impressora'] >= start_date_impressora) & (df['data_impressora'] <= end_date_impressora)]
        start_date_robo = request.args.get('start_date_robo')
        end_date_robo = request.args.get('end_date_robo')
        if start_date_robo and end_date_robo:
            df = df[(df['data_robo'] >= start_date_robo) & (df['data_robo'] <= end_date_robo)]
        start_date_inspecao = request.args.get('start_date_inspecao')
        end_date_inspecao = request.args.get('end_date_inspecao')
        if start_date_inspecao and end_date_inspecao:
            df = df[(df['data_inspecao'] >= start_date_inspecao) & (df['data_inspecao'] <= end_date_inspecao)]
        selected_operadores = request.args.getlist('operadores')
        if selected_operadores:
            df = df[df['operador'].isin(selected_operadores)]
        selected_maquinas = request.args.getlist('maquinas')
        if selected_maquinas:
            df = df[df['sos'].isin(selected_maquinas)]
        selected_tipos_impressao = request.args.getlist('tipos_impressao')
        if selected_tipos_impressao:
            df = df[df['tipo_impressao'].isin(selected_tipos_impressao)]
        
        # OrdenaÃ§Ã£o: por padrÃ£o Data InspeÃ§Ã£o Final (mais recente primeiro)
        sort_by = request.args.get('sort_by', 'data_inspecao')
        sort_order = request.args.get('sort_order', 'desc')
        allowed_sort_columns = [
            'id', 'num_of', 'data_inspecao', 'quantidade_comanda', 'quantidade_inspecao_geral', 
            'perdas_un', 'refugo_robo', 'refugo_inspecao_final', 'perdas_geral', 'pct_refugo_pedido', 'refugo_flexo_kg', 'refugo_sos_kg', 'consumo_total',
            'servico', 'numero_pedido'
        ]
        if sort_by not in allowed_sort_columns:
            sort_by = 'data_inspecao'
        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'
        if sort_by in df.columns:
            if sort_by == 'data_inspecao':
                df[sort_by] = pd.to_datetime(df[sort_by], errors='coerce')
            df = df.sort_values(by=sort_by, ascending=(sort_order == 'asc'), na_position='last')
            # Reverter data_inspecao para string YYYY-MM-DD para o template exibir DD/MM/YYYY sem horÃ¡rio
            if sort_by == 'data_inspecao' and 'data_inspecao' in df.columns:
                df['data_inspecao'] = df['data_inspecao'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else None)
        
        # Converter para lista de dicionÃ¡rios
        lancamentos = df.to_dict('records')
        
        # Importar math para arredondar para cima
        import math
        
        # Calcular consumo_total e arredondar quantidades e refugos para cima
        campos_arredondar = ['quantidade_comanda', 'quantidade_inspecao_geral', 'perdas_un', 'refugo_robo', 'refugo_inspecao_final', 'perdas_geral']
        for lancamento in lancamentos:
            # Arredondar quantidades e refugos para cima
            for campo in campos_arredondar:
                if campo in lancamento and lancamento[campo] is not None:
                    try:
                        valor = float(lancamento[campo])
                        lancamento[campo] = math.ceil(valor)
                    except (ValueError, TypeError):
                        pass
            
            # Refugo Flexo (kg) = refugo_acerto_flexo + refugo_flexo + refugo_pre_impresso
            refugo_acerto_flexo = float(lancamento.get('refugo_acerto_flexo', 0) or 0)
            refugo_flexo = float(lancamento.get('refugo_flexo', 0) or 0)
            refugo_pre_impresso = float(lancamento.get('refugo_pre_impresso', 0) or 0)
            lancamento['refugo_flexo_kg'] = refugo_acerto_flexo + refugo_flexo + refugo_pre_impresso
            
            # Refugo SOS (kg) = refugo_acerto_sos + refugo_sos (sem refugo_pre_impresso na tela OF-Refugo)
            refugo_acerto_sos = float(lancamento.get('refugo_acerto_sos', 0) or 0)
            refugo_sos = float(lancamento.get('refugo_sos', 0) or 0)
            lancamento['refugo_sos_kg'] = refugo_acerto_sos + refugo_sos
            
            # Calcular consumo_total se necessÃ¡rio (Consumo Util + Refugo Geral kg)
            if 'consumo_total' not in lancamento or lancamento['consumo_total'] is None or lancamento['consumo_total'] == 0:
                consumo_util = lancamento.get('consumo_util', 0) or 0
                perdas_geral_kg = float(lancamento.get('perdas_geral_kg', 0) or 0)
                lancamento['consumo_total'] = consumo_util + perdas_geral_kg
            
            # Porcentagem de Refugo Pedido = Refugo Geral PeÃ§as / (Qtde InspeÃ§Ã£o Final + Refugo Geral PeÃ§as) Ã— 100
            qtd_inspecao = float(lancamento.get('quantidade_inspecao_geral', 0) or 0)
            perdas_geral_val = float(lancamento.get('perdas_geral', 0) or 0)
            denominador = qtd_inspecao + perdas_geral_val
            lancamento['pct_refugo_pedido'] = (perdas_geral_val / denominador * 100) if denominador > 0 else None
    
    preserved_args = request.args.to_dict()
    preserved_args.pop('sort_by', None)
    preserved_args.pop('sort_order', None)
    preserved_args.pop('page', None)
    total_registros_filtrados = len(lancamentos)
    
    # ExportaÃ§Ã£o para Excel
    if request.args.get("export") == "excel":
        if lancamentos:
            # Campos simplificados para exibir
            column_order = ['num_of', 'servico', 'numero_pedido', 'data_inspecao', 'quantidade_comanda', 'quantidade_inspecao_geral', 'perdas_geral', 'pct_refugo_pedido', 'perdas_un', 'refugo_robo', 'refugo_inspecao_final', 'refugo_flexo_kg', 'refugo_sos_kg', 'consumo_total']
            
            df_data = []
            for lancamento in lancamentos:
                row = {}
                for col in column_order:
                    if col in lancamento:
                        row[col] = lancamento[col]
                df_data.append(row)
            
            df = pd.DataFrame(df_data)
            available_columns = [col for col in column_order if col in df.columns]
            df = df[available_columns]
            
            column_names = {
                'num_of': 'NÂº OF',
                'servico': 'ServiÃ§o',
                'numero_pedido': 'NÃºmero do Pedido',
                'data_inspecao': 'Data InspeÃ§Ã£o Final',
                'quantidade_comanda': 'Qtde Comanda',
                'quantidade_inspecao_geral': 'Qtde InspeÃ§Ã£o Final',
                'perdas_un': 'Refugo ProduÃ§Ã£o (peÃ§as)',
                'refugo_robo': 'Refugo Robo (peÃ§as)',
                'refugo_inspecao_final': 'Refugo InspeÃ§Ã£o Final (peÃ§as)',
                'perdas_geral': 'Refugo Geral PeÃ§as',
                'pct_refugo_pedido': 'Porcentagem de Refugo Pedido',
                'refugo_flexo_kg': 'Refugo Flexo (kg)',
                'refugo_sos_kg': 'Refugo SOS (kg)',
                'consumo_total': 'Consumo Total (kg)'
            }
            df = df.rename(columns=column_names)
            
            for col in ['Data InspeÃ§Ã£o Final']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            import math
            # Campos numÃ©ricos inteiros (arredondados para cima)
            int_cols = ['NÃºmero do Pedido', 'Qtde Comanda', 'Qtde InspeÃ§Ã£o Final', 'Refugo ProduÃ§Ã£o (peÃ§as)', 'Refugo Robo (peÃ§as)', 'Refugo InspeÃ§Ã£o Final (peÃ§as)', 'Refugo Geral PeÃ§as']
            for col in int_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').apply(lambda x: math.ceil(x) if pd.notna(x) else x).astype('Int64')
            
            # Campos numÃ©ricos decimais
            numeric_cols = ['Refugo Flexo (kg)', 'Refugo SOS (kg)', 'Consumo Total (kg)']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            # Porcentagem de Refugo Pedido: converter de 5.5 para 0.055 para formato % no Excel
            if 'Porcentagem de Refugo Pedido' in df.columns:
                df['Porcentagem de Refugo Pedido'] = pd.to_numeric(df['Porcentagem de Refugo Pedido'], errors='coerce') / 100.0
            
            output = BytesIO()
            try:
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='OF-Refugo')
                    if not df.empty:
                        workbook = writer.book
                        ws = writer.sheets['OF-Refugo']
                        fmt_number = workbook.add_format({'num_format': '#,##0.00'})
                        fmt_int = workbook.add_format({'num_format': '#,##0'})
                        fmt_date = workbook.add_format({'num_format': 'dd/mm/yyyy'})
                        fmt_percent = workbook.add_format({'num_format': '0.00%'})
                        
                        # Cores para cabeÃ§alhos especÃ­ficos
                        header_colors = {
                            'Refugo Flexo (kg)': '#ffeaa7',  # Laranja pastel clarinho
                            'Refugo SOS (kg)': '#ffeaa7',     # Laranja pastel clarinho
                            'Consumo Total (kg)': '#ffeaa7',  # Laranja pastel clarinho
                            'Porcentagem de Refugo Pedido': '#d4edda'  # Verde pastel (igual Refugo Geral)
                        }
                        
                        for i, col in enumerate(df.columns):
                            bg_color = header_colors.get(col, '#f8f9fa')  # Cor padrÃ£o se nÃ£o encontrada
                            header_format = workbook.add_format({
                                'bold': True,
                                'bg_color': bg_color,
                                'border': 1,
                                'align': 'center',
                                'valign': 'vcenter'
                            })
                            ws.write(0, i, col, header_format)
                            s = df[col].apply(lambda x: str(x) if pd.notna(x) else '')
                            width = max(int(s.str.len().max()) if len(s) > 0 else 0, len(col)) + 2
                            if col in int_cols:
                                ws.set_column(i, i, width, fmt_int)
                            elif col in numeric_cols:
                                ws.set_column(i, i, width, fmt_number)
                            elif col == 'Porcentagem de Refugo Pedido':
                                ws.set_column(i, i, width, fmt_percent)
                            elif col == 'Data InspeÃ§Ã£o Final':
                                ws.set_column(i, i, width, fmt_date)
                            else:
                                ws.set_column(i, i, width)
                output.seek(0)
                return send_file(output, download_name="of_refugo.xlsx", as_attachment=True)
            except Exception as e:
                flash(f"Erro ao exportar: {e}", "danger")
                return redirect(url_for('main.of_refugo'))
    
    pagination_args = request.args.to_dict()
    pagination_args.pop('page', None)
    per_page = 100
    total_paginas = max(1, (total_registros_filtrados + per_page - 1) // per_page)
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    page = max(1, min(page, total_paginas))
    offset = (page - 1) * per_page
    lancamentos_pagina = lancamentos[offset:offset + per_page]

    contexto = dict(
        lancamentos=lancamentos_pagina, all_operadores=ALL_OPERADORES,
        preserved_args=preserved_args, pagination_args=pagination_args, action_url=url_for('main.of_refugo'),
        page=page, total_paginas=total_paginas, total_registros=total_registros_filtrados, per_page=per_page
    )
    if request.headers.get('HX-Request') == 'true':
        return render_template('partials/of_refugo_resultado.html', **contexto)
    return render_template('historico_simplificado.html', **contexto)

@main_bp.route("/historico_simplificado")
def historico_simplificado_redirect():
    """Redirect da URL antiga para /of-refugo (preserva filtros e parÃ¢metros)."""
    return redirect(url_for('main.of_refugo', **request.args))

# ComparaÃ§Ã£o Quantidade (duplicata OF-Refugo com colunas especÃ­ficas + Refugo SOS PeÃ§as e DiferenÃ§a)
@main_bp.route("/comparacao-quantidade")
def comparacao_quantidade():
    import math
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM producao", conn)
    conn.close()

    lancamentos = []

    if not df.empty:
        servico = request.args.get('servico', '').strip()
        if servico:
            df = df[df['servico'].str.contains(servico, case=False, na=False)]
        num_of = request.args.get('num_of', '').strip()
        if num_of:
            df = df[df['num_of'].str.contains(num_of, case=False, na=False)]
        numero_pedido = request.args.get('numero_pedido', '').strip()
        if numero_pedido and 'numero_pedido' in df.columns:
            df = df[df['numero_pedido'].astype(str).str.contains(numero_pedido, case=False, na=False)]
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if start_date and end_date:
            df = df[(df['data'] >= start_date) & (df['data'] <= end_date)]
        start_date_impressora = request.args.get('start_date_impressora')
        end_date_impressora = request.args.get('end_date_impressora')
        if start_date_impressora and end_date_impressora:
            df = df[(df['data_impressora'] >= start_date_impressora) & (df['data_impressora'] <= end_date_impressora)]
        start_date_robo = request.args.get('start_date_robo')
        end_date_robo = request.args.get('end_date_robo')
        if start_date_robo and end_date_robo:
            df = df[(df['data_robo'] >= start_date_robo) & (df['data_robo'] <= end_date_robo)]
        start_date_inspecao = request.args.get('start_date_inspecao')
        end_date_inspecao = request.args.get('end_date_inspecao')
        if start_date_inspecao and end_date_inspecao:
            df = df[(df['data_inspecao'] >= start_date_inspecao) & (df['data_inspecao'] <= end_date_inspecao)]
        selected_operadores = request.args.getlist('operadores')
        if selected_operadores:
            df = df[df['operador'].isin(selected_operadores)]
        selected_maquinas = request.args.getlist('maquinas')
        if selected_maquinas:
            df = df[df['sos'].isin(selected_maquinas)]
        selected_tipos_impressao = request.args.getlist('tipos_impressao')
        if selected_tipos_impressao:
            df = df[df['tipo_impressao'].isin(selected_tipos_impressao)]

        # ComparaÃ§Ã£o Quantidade: excluir linhas com quantidade_impressora 0 ou null
        if 'quantidade_impressora' in df.columns:
            df = df[(df['quantidade_impressora'].notna()) & (df['quantidade_impressora'] != 0)]
        # Excluir linhas com Quantidade SOS igual a 0
        if 'quantidade' in df.columns:
            df = df[(df['quantidade'].notna()) & (df['quantidade'] != 0)]

        sort_by = request.args.get('sort_by', 'id')
        sort_order = request.args.get('sort_order', 'desc')
        allowed_sort = [
            'id', 'num_of', 'servico', 'numero_pedido', 'quantidade_comanda', 'quantidade_impressora', 'quantidade',
            'refugo_sos_pecas', 'diferenca', 'observacoes'
        ]
        if sort_by not in allowed_sort:
            sort_by = 'id'
        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'

        rows = df.to_dict('records')
        for r in rows:
            ras = float(r.get('refugo_acerto_sos', 0) or 0)
            rpi = float(r.get('refugo_pre_impresso', 0) or 0)
            rs = float(r.get('refugo_sos', 0) or 0)
            refugo_sos_kg = ras + rpi + rs
            m = float(r.get('milheiro', 0) or 0)
            refugo_sos_pecas = math.ceil((refugo_sos_kg * 1000) / m) if m > 0 else 0
            qsos = int(r.get('quantidade', 0) or 0)
            qimp = int(r.get('quantidade_impressora', 0) or 0)
            diferenca = (qsos + refugo_sos_pecas) - qimp

            rec = {
                'id': r.get('id'),
                'num_of': r.get('num_of'),
                'servico': r.get('servico'),
                'numero_pedido': r.get('numero_pedido'),
                'quantidade_comanda': r.get('quantidade_comanda'),
                'quantidade': r.get('quantidade'),
                'quantidade_impressora': r.get('quantidade_impressora'),
                'refugo_sos_pecas': refugo_sos_pecas,
                'diferenca': diferenca,
                'observacoes': r.get('observacoes'),
            }
            if rec['quantidade_comanda'] is not None:
                try:
                    rec['quantidade_comanda'] = math.ceil(float(rec['quantidade_comanda']))
                except (ValueError, TypeError):
                    pass
            lancamentos.append(rec)

        if lancamentos and sort_by in allowed_sort:
            d = pd.DataFrame(lancamentos)
            if sort_by in d.columns:
                d = d.sort_values(by=sort_by, ascending=(sort_order == 'asc'), na_position='last')
            lancamentos = d.to_dict('records')

    preserved_args = request.args.to_dict()
    preserved_args.pop('sort_by', None)
    preserved_args.pop('sort_order', None)
    preserved_args.pop('page', None)
    total_registros_filtrados = len(lancamentos)

    if request.args.get("export") == "excel" and lancamentos:
        column_order = ['num_of', 'servico', 'numero_pedido', 'quantidade_comanda', 'quantidade_impressora', 'quantidade', 'refugo_sos_pecas', 'diferenca', 'observacoes']
        column_names = {
            'num_of': 'NÂº OF', 'servico': 'ServiÃ§o', 'numero_pedido': 'NÃºmero do Pedido',
            'quantidade_comanda': 'Quantidade Comanda', 'quantidade': 'Quantidade SOS', 'quantidade_impressora': 'Quantidade Impressora',
            'refugo_sos_pecas': 'Refugo SOS PeÃ§as', 'diferenca': 'DiferenÃ§a', 'observacoes': 'ObservaÃ§Ãµes'
        }
        df_out = pd.DataFrame(lancamentos)
        df_out = df_out[[c for c in column_order if c in df_out.columns]]
        df_out = df_out.rename(columns=column_names)
        int_cols = ['NÃºmero do Pedido', 'Quantidade Comanda', 'Quantidade SOS', 'Quantidade Impressora', 'Refugo SOS PeÃ§as', 'DiferenÃ§a']
        for col in int_cols:
            if col in df_out.columns:
                df_out[col] = pd.to_numeric(df_out[col], errors='coerce').apply(lambda x: math.ceil(x) if pd.notna(x) else x).astype('Int64')
        output = BytesIO()
        try:
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_out.to_excel(writer, index=False, sheet_name='Comparacao Quantidade')
                if not df_out.empty:
                    wb = writer.book
                    ws = writer.sheets['Comparacao Quantidade']
                    fmt = wb.add_format({'bold': True, 'bg_color': '#f8f9fa', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
                    fmt_int = wb.add_format({'num_format': '#,##0'})
                    int_cols = ['NÃºmero do Pedido', 'Quantidade Comanda', 'Quantidade SOS', 'Quantidade Impressora', 'Refugo SOS PeÃ§as', 'DiferenÃ§a']
                    for i, col in enumerate(df_out.columns):
                        ws.write(0, i, col, fmt)
                        mx = df_out.iloc[:, i].astype(str).str.len().max()
                        w = max(int(mx) if pd.notna(mx) else 0, len(str(col))) + 2
                        ws.set_column(i, i, w, fmt_int if col in int_cols else None)
            output.seek(0)
            return send_file(output, download_name="comparacao_quantidade.xlsx", as_attachment=True)
        except Exception as e:
            flash(f"Erro ao exportar: {e}", "danger")
            return redirect(url_for('main.comparacao_quantidade'))

    pagination_args = request.args.to_dict()
    pagination_args.pop('page', None)
    per_page = 100
    total_paginas = max(1, (total_registros_filtrados + per_page - 1) // per_page)
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    page = max(1, min(page, total_paginas))
    offset = (page - 1) * per_page
    lancamentos_pagina = lancamentos[offset:offset + per_page]

    contexto = dict(
        lancamentos=lancamentos_pagina, all_operadores=ALL_OPERADORES,
        preserved_args=preserved_args, pagination_args=pagination_args, action_url=url_for('main.comparacao_quantidade'),
        page=page, total_paginas=total_paginas, total_registros=total_registros_filtrados, per_page=per_page
    )
    if request.headers.get('HX-Request') == 'true':
        return render_template('partials/comparacao_quantidade_resultado.html', **contexto)
    return render_template('comparacao_quantidade.html', **contexto)

