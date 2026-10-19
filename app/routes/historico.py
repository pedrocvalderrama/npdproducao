"""Rota de histÃ³rico de lanÃ§amentos (listagem, filtros, paginaÃ§Ã£o, exportaÃ§Ã£o)."""
from flask import render_template, request, flash, send_file, redirect, url_for, session, jsonify
from datetime import datetime
import pandas as pd
from io import BytesIO
from ..models import get_db_connection, inicializar_banco
from ..business import calcular_metricas_producao, calc_tempo_producao_impressora, enrich_lancamento_observacoes, get_seconds_from_time, observacoes_from_form
from ..config import ALL_OPERADORES, ALL_MAQUINAS, MAQUINAS_SOS, OPERADORES_SOS, OPERADORES_IMPRESSORA, OPERADORES_ROBO
from ..utils import safe_get_int, safe_get_float, safe_get_str
from . import main_bp

# Rota para exibir o histÃ³rico de lanÃ§amentos, com filtros e exportaÃ§Ã£o
@main_bp.route("/historico")
def historico():
    conn = get_db_connection()
    query = "SELECT * FROM producao WHERE 1=1"
    params = []
    args = request.args.copy()
    # Filtros por operador
    selected_ops = args.getlist('operadores')
    if selected_ops:
        query += f" AND operador IN ({','.join(['?']*len(selected_ops))})"
        params.extend(selected_ops)
    # Filtros por mÃ¡quina
    selected_maqs = args.getlist('maquinas')
    if selected_maqs:
        query += f" AND sos IN ({','.join(['?']*len(selected_maqs))})"
        params.extend(selected_maqs)
    # Filtros por tipo de impressÃ£o
    selected_tipos_impressao = args.getlist('tipos_impressao')
    if selected_tipos_impressao:
        query += f" AND tipo_impressao IN ({','.join(['?']*len(selected_tipos_impressao))})"
        params.extend(selected_tipos_impressao)
    # Filtro por NÂº de OF
    num_of = args.get('num_of', '').strip()
    if num_of:
        query += " AND num_of LIKE ?"
        params.append(f"%{num_of}%")
    # Filtro por NÂº de Pedido
    numero_pedido = args.get('numero_pedido', '').strip()
    if numero_pedido:
        query += " AND CAST(numero_pedido AS TEXT) LIKE ?"
        params.append(f"%{numero_pedido}%")
    # Filtro por ServiÃ§o (busca parcial)
    servico = args.get('servico', '').strip()
    if servico:
        query += " AND servico LIKE ?"
        params.append(f"%{servico}%")
    # Filtros por data SOS
    start_date = args.get('start_date'); end_date = args.get('end_date')
    if start_date and end_date:
        query += " AND data BETWEEN ? AND ?"; params.extend([start_date, end_date])
    # Filtros por data Impressora
    start_date_impressora = args.get('start_date_impressora'); end_date_impressora = args.get('end_date_impressora')
    if start_date_impressora and end_date_impressora:
        query += " AND data_impressora BETWEEN ? AND ?"; params.extend([start_date_impressora, end_date_impressora])
    # Filtros por data RobÃ´
    start_date_robo = args.get('start_date_robo'); end_date_robo = args.get('end_date_robo')
    if start_date_robo and end_date_robo:
        query += " AND data_robo BETWEEN ? AND ?"; params.extend([start_date_robo, end_date_robo])
    # Filtros por data InspeÃ§Ã£o
    start_date_inspecao = args.get('start_date_inspecao'); end_date_inspecao = args.get('end_date_inspecao')
    if start_date_inspecao and end_date_inspecao:
        query += " AND data_inspecao BETWEEN ? AND ?"; params.extend([start_date_inspecao, end_date_inspecao])
    # OrdenaÃ§Ã£o
    sort_by = args.get('sort_by', 'id'); sort_order = args.get('sort_order', 'desc')
    allowed_sort_columns = [
        'id', 'num_of', 'data', 'data_impressora', 'data_inspecao', 'data_robo', 'operador', 'operador_impressora', 'operador_robo', 'impressora', 'sos', 'robo_alca', 'qtd_cliches', 'tipo', 'formato', 
        'papel', 'servico', 'milheiro', 'tipo_impressao', 'quantidade_comanda', 'quantidade', 'quantidade_impressora', 'quantidade_inspecao_geral', 'quantidade_robo', 'refugo_flexo', 'refugo_pre_impresso', 'refugo_sos',
        'refugo_robo', 'refugo_inspecao_final', 'refugo_robo_kg', 'refugo_inspecao_final_kg', 'refugo_acerto_flexo', 'refugo_acerto_sos', 'refugo_pct', 'refugo_pct_flexo', 'eficiencia_pct', 'velocidade_un_min', 'velocidade_un_min_flexo', 
        'refugo_producao_total', 'consumo_util', 'consumo_total', 'perdas_un', 'perdas_geral', 'perdas_geral_kg', 'tempo_prod_s', 'tempo_acerto_s', 'tempo_prod_impressora', 'tempo_acerto_impressora', 'inicio_acerto', 'fim_acerto', 'inicio_acerto_impressora', 'fim_acerto_impressora', 'inicio_prod', 'fim_prod', 'inicio_prod_impressora', 'fim_prod_impressora', 'operador_impressora', 'numero_pedido'
    ]
    if sort_by not in allowed_sort_columns: sort_by = 'id'
    if sort_order not in ['asc', 'desc']: sort_order = 'desc'
    # Guarda a query com filtros (sem ORDER BY/LIMIT) para gerar a contagem total
    query_where = query
    query += f" ORDER BY {sort_by} {sort_order}"

    is_export = args.get("export") == "excel"
    PER_PAGE = 100

    if is_export:
        # ExportaÃ§Ã£o sempre traz o conjunto completo filtrado, sem paginaÃ§Ã£o
        lancamentos_raw = conn.execute(query, tuple(params)).fetchall()
        lancamentos = [dict(row) for row in lancamentos_raw]
        page = 1
        total_registros = len(lancamentos)
        total_paginas = 1
    else:
        count_query = query_where.replace("SELECT * FROM producao", "SELECT COUNT(*) AS total FROM producao", 1)
        total_registros = conn.execute(count_query, tuple(params)).fetchone()['total']
        total_paginas = max(1, (total_registros + PER_PAGE - 1) // PER_PAGE)
        try:
            page = int(args.get('page', 1))
        except (TypeError, ValueError):
            page = 1
        page = max(1, min(page, total_paginas))
        offset = (page - 1) * PER_PAGE
        lancamentos_raw = conn.execute(query + " LIMIT ? OFFSET ?", tuple(params) + (PER_PAGE, offset)).fetchall()
        lancamentos = [dict(row) for row in lancamentos_raw]

    # Garantir que todos os registros tenham as colunas calculadas
    for lancamento in lancamentos:
        # Consumo util: mesma lógica do lançamento de custo → (Quantidade SOS / 1000) × milheiro
        quantidade_sos = float(lancamento.get('quantidade', 0) or 0)
        milheiro = float(lancamento.get('milheiro', 0) or 0)
        lancamento['consumo_util'] = (quantidade_sos / 1000.0) * milheiro

        # Consumo total: Consumo Util + Refugo Geral (kg)
        perdas_geral_kg = float(lancamento.get('perdas_geral_kg', 0) or 0)
        lancamento['consumo_total'] = lancamento['consumo_util'] + perdas_geral_kg
    preserved_args = args.copy()
    preserved_args.pop('sort_by', None); preserved_args.pop('sort_order', None); preserved_args.pop('page', None)
    pagination_args = args.copy()
    pagination_args.pop('page', None)
    # A conexÃ£o nÃ£o Ã© mais necessÃ¡ria a partir daqui (dados jÃ¡ carregados em
    # `lancamentos`); fecha jÃ¡ para nÃ£o depender do sucesso da geraÃ§Ã£o do Excel.
    conn.close()
    # ExportaÃ§Ã£o para Excel
    if args.get("export") == "excel":
        if lancamentos:
            # Definir a mesma ordem de colunas da tabela do histÃ³rico (conforme ordem colunas.xlsx)
            column_order = ['num_of', 'servico', 'numero_pedido', 'papel', 'formato', 'tipo', 'qtd_cliches', 'milheiro', 'quantidade_comanda', 'impressora', 'data_impressora', 'operador_impressora', 'quantidade_impressora', 'refugo_acerto_flexo', 'refugo_flexo', 'refugo_pre_impresso', 'refugo_pct_flexo', 'velocidade_un_min_flexo', 'tempo_acerto_impressora', 'tempo_prod_impressora', 'inicio_acerto_impressora', 'fim_acerto_impressora', 'inicio_prod_impressora', 'fim_prod_impressora', 'sos', 'data', 'operador', 'quantidade', 'tipo_impressao', 'refugo_acerto_sos', 'refugo_sos', 'refugo_pct', 'velocidade_un_min', 'tempo_acerto_s', 'tempo_prod_s', 'inicio_acerto', 'fim_acerto', 'inicio_prod', 'fim_prod', 'perdas_un', 'refugo_producao_total', 'consumo_util', 'consumo_total', 'robo_alca', 'data_robo', 'operador_robo', 'quantidade_robo', 'refugo_robo', 'refugo_robo_kg', 'data_inspecao', 'quantidade_inspecao_geral', 'refugo_inspecao_final', 'refugo_inspecao_final_kg', 'perdas_geral', 'perdas_geral_kg', 'observacoes', 'inicio_prod_2', 'fim_prod_2', 'eficiencia_pct']
            
            # Criar DataFrame com dados ordenados
            df_data = []
            for lancamento in lancamentos:
                row = {}
                for col in column_order:
                    if col in lancamento:
                        row[col] = lancamento[col]
                df_data.append(row)
            
            df = pd.DataFrame(df_data)
            
            # Reordenar colunas para seguir a ordem definida
            available_columns = [col for col in column_order if col in df.columns]
            df = df[available_columns]
            
            # Renomear colunas para nomes mais amigÃ¡veis
            column_names = {
                'num_of': 'NÂº OF',
                'servico': 'ServiÃ§o',
                'data': 'Data SOS',
                'data_impressora': 'Data Impressora',
                'data_inspecao': 'Data InspeÃ§Ã£o',
                'data_robo': 'Data RobÃ´',
                'quantidade_comanda': 'Quantidade Comanda',
                'quantidade': 'Quantidade SOS',
                'quantidade_impressora': 'Quantidade Impressora',
                'quantidade_inspecao_geral': 'Quantidade InspeÃ§Ã£o Final',
                'quantidade_robo': 'Quantidade RobÃ´',
                'impressora': 'Impressora',
                'sos': 'SOS',
                'robo_alca': 'RobÃ´ AlÃ§a',
                'operador': 'Operador SOS',
                'operador_impressora': 'Operador Impressora',
                'operador_robo': 'Operador Robo',
                'papel': 'Papel',
                'formato': 'Formato',
                'tipo': 'Tipo',
                'qtd_cliches': 'Qtd. ClichÃªs',
                'milheiro': 'Peso Milheiro',
                'tipo_impressao': 'Tipo ImpressÃ£o',
                'refugo_flexo': 'Refugo Flexo',
                'refugo_pre_impresso': 'Refugo PrÃ©-Impresso',
                'refugo_sos': 'Refugo SOS',
                'refugo_robo': 'Refugo Robo (peÃ§as)',
                'refugo_inspecao_final': 'Refugo InspeÃ§Ã£o Final (peÃ§as)',
                'refugo_robo_kg': 'Refugo RobÃ´ (kg)',
                'refugo_inspecao_final_kg': 'Refugo InspeÃ§Ã£o Final (kg)',
                'refugo_acerto_flexo': 'Refugo Acerto Flexo',
                'refugo_acerto_sos': 'Refugo Acerto SOS',
                'refugo_producao_total': 'Refugo ProduÃ§Ã£o Total (kg)',
                'consumo_util': 'Consumo Util',
                'consumo_total': 'Consumo Total',
                'inicio_acerto': 'InÃ­cio Acerto SOS',
                'fim_acerto': 'Fim Acerto SOS',
                'inicio_acerto_impressora': 'InÃ­cio Acerto Impressora',
                'fim_acerto_impressora': 'Fim Acerto Impressora',
                'inicio_prod': 'InÃ­cio ProduÃ§Ã£o SOS',
                'fim_prod': 'Fim ProduÃ§Ã£o SOS',
                'inicio_prod_impressora': 'InÃ­cio ProduÃ§Ã£o Impressora',
                'fim_prod_impressora': 'Fim ProduÃ§Ã£o Impressora',
                'inicio_prod_impressora_2': 'InÃ­cio ProduÃ§Ã£o Impressora 2',
                'fim_prod_impressora_2': 'Fim ProduÃ§Ã£o Impressora 2',
                'inicio_prod_impressora_3': 'InÃ­cio ProduÃ§Ã£o Impressora 3',
                'fim_prod_impressora_3': 'Fim ProduÃ§Ã£o Impressora 3',
                'inicio_prod_impressora_4': 'InÃ­cio ProduÃ§Ã£o Impressora 4',
                'fim_prod_impressora_4': 'Fim ProduÃ§Ã£o Impressora 4',
                'tempo_acerto_s': 'Tempo Acerto SOS',
                'tempo_prod_s': 'Tempo ProduÃ§Ã£o SOS',
                'tempo_acerto_impressora': 'Tempo Acerto Impressora',
                'tempo_prod_impressora': 'Tempo ProduÃ§Ã£o Impressora',
                'perdas_un': 'Refugo ProduÃ§Ã£o (PeÃ§as)',
                'perdas_geral': 'Refugo Geral PeÃ§as',
                'perdas_geral_kg': 'Refugo Geral (kg)',
                'inicio_prod_2': 'InÃ­cio ProduÃ§Ã£o 2',
                'fim_prod_2': 'Fim ProduÃ§Ã£o 2',
                'inicio_prod_3': 'InÃ­cio ProduÃ§Ã£o 3',
                'fim_prod_3': 'Fim ProduÃ§Ã£o 3',
                'inicio_prod_4': 'InÃ­cio ProduÃ§Ã£o 4',
                'fim_prod_4': 'Fim ProduÃ§Ã£o 4',
                'velocidade_un_min': 'Velocidade SOS',
                'velocidade_un_min_flexo': 'Velocidade Impressora',
                'refugo_pct': 'Refugo Porcentagem SOS',
                'refugo_pct_flexo': 'Refugo Porcentagem Impressora',
                'observacoes': 'ObservaÃ§Ãµes'
            }
            
            df = df.rename(columns=column_names)

            # Converter Data para datetime (Excel aplicarÃ¡ a localidade ao exibir)
            for col in ['Data SOS', 'Data Impressora', 'Data InspeÃ§Ã£o', 'Data RobÃ´']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')

            # Manter percentuais e numÃ©ricos como valores numÃ©ricos; Excel exibirÃ¡ com vÃ­rgula baseado na localidade
            numeric_cols = ['Quantidade Comanda', 'Quantidade SOS', 'Quantidade Impressora', 'Quantidade InspeÃ§Ã£o Final', 'Quantidade RobÃ´', 'Qtd. ClichÃªs', 'Peso Milheiro', 'Refugo Flexo', 'Refugo PrÃ©-Impresso', 'Refugo SOS', 'Refugo Robo (peÃ§as)', 'Refugo InspeÃ§Ã£o Final (peÃ§as)', 'Refugo RobÃ´ (kg)', 'Refugo InspeÃ§Ã£o Final (kg)', 'Refugo Acerto Flexo', 'Refugo Acerto SOS', 'Refugo ProduÃ§Ã£o Total (kg)', 'Consumo Util', 'Consumo Total', 'Refugo ProduÃ§Ã£o (PeÃ§as)', 'Refugo Geral PeÃ§as', 'Refugo Geral (kg)', 'Velocidade SOS', 'Velocidade Impressora']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            for col in ['Refugo Porcentagem SOS', 'Refugo Porcentagem Impressora', '% EficiÃªncia']:
                if col in df.columns:
                    # Valores vÃªm como 1.21 para 1.21%, Excel espera 0.0121 para exibir 1.21%
                    df[col] = pd.to_numeric(df[col], errors='coerce') / 100.0

            # Converter tempo (segundos) para fraÃ§Ã£o de dia (Excel) como nÃºmero
            for col in ['Tempo Acerto SOS', 'Tempo ProduÃ§Ã£o SOS', 'Tempo Acerto Impressora', 'Tempo ProduÃ§Ã£o Impressora']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: (float(x) / 86400.0) if pd.notna(x) and x != '' and float(x) > 0 else pd.NA)
            
        else:
            df = pd.DataFrame()
        
        output = BytesIO()
        try:
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Historico')
                if not df.empty:
                    workbook = writer.book
                    ws = writer.sheets['Historico']
                    fmt_number = workbook.add_format({'num_format': '#,##0.00'})
                    fmt_percent = workbook.add_format({'num_format': '0.00%'})
                    fmt_time = workbook.add_format({'num_format': '[h]:mm:ss'})
                    fmt_date = workbook.add_format({'num_format': 'dd/mm/yyyy'})
                    
                    # Mapeamento de cores para cabeÃ§alhos (cores pastel em RGB)
                    header_colors = {
                        # Verde pastel claro para datas
                        'Data Impressora': '#d4edda',
                        'Data SOS': '#d4edda',
                        'Data RobÃ´': '#d4edda',
                        'Data InspeÃ§Ã£o': '#d4edda',
                        # Azul pastel claro para quantidades
                        'Quantidade Comanda': '#d1ecf1',
                        'Quantidade SOS': '#d1ecf1',
                        'Quantidade Impressora': '#d1ecf1',
                        'Quantidade InspeÃ§Ã£o Final': '#d1ecf1',
                        'Quantidade RobÃ´': '#d1ecf1',
                        # Laranja pastel claro para impressora atÃ© tipo de impressÃ£o
                        'Impressora': '#ffeaa7',
                        'SOS': '#ffeaa7',
                        'RobÃ´ AlÃ§a': '#ffeaa7',
                        'Operador SOS': '#ffeaa7',
                        'Operador Impressora': '#ffeaa7',
                        'Operador Robo': '#ffeaa7',
                        'Papel': '#ffeaa7',
                        'Formato': '#ffeaa7',
                        'Tipo': '#ffeaa7',
                        'Qtd. ClichÃªs': '#ffeaa7',
                        'Peso Milheiro': '#ffeaa7',
                        'Tipo ImpressÃ£o': '#ffeaa7',
                        # Verde pastel claro para refugo
                        'Refugo Acerto Flexo': '#d4edda',
                        'Refugo Flexo': '#d4edda',
                        'Refugo Acerto SOS': '#d4edda',
                        'Refugo PrÃ©-Impresso': '#d4edda',
                        'Refugo SOS': '#d4edda',
                        'Refugo ProduÃ§Ã£o Total (kg)': '#d4edda',
                        # Azul pastel claro para refugo produÃ§Ã£o atÃ© consumo total
                        'Refugo ProduÃ§Ã£o (PeÃ§as)': '#d1ecf1',
                        'Refugo Robo (peÃ§as)': '#d1ecf1',
                        'Refugo InspeÃ§Ã£o Final (peÃ§as)': '#d1ecf1',
                        'Refugo RobÃ´ (kg)': '#d1ecf1',
                        'Refugo InspeÃ§Ã£o Final (kg)': '#d1ecf1',
                        'Refugo Geral PeÃ§as': '#d1ecf1',
                        'Refugo Geral (kg)': '#d1ecf1',
                        'Consumo Util': '#d1ecf1',
                        'Consumo Total': '#d1ecf1',
                        # Amarelo pastel claro para impressora
                        'InÃ­cio Acerto Impressora': '#fff9c4',
                        'Fim Acerto Impressora': '#fff9c4',
                        'InÃ­cio ProduÃ§Ã£o Impressora': '#fff9c4',
                        'Fim ProduÃ§Ã£o Impressora': '#fff9c4',
                        'Tempo Acerto Impressora': '#fff9c4',
                        'Tempo ProduÃ§Ã£o Impressora': '#fff9c4',
                        # Verde pastel claro para SOS
                        'InÃ­cio Acerto SOS': '#d4edda',
                        'Fim Acerto SOS': '#d4edda',
                        'InÃ­cio ProduÃ§Ã£o SOS': '#d4edda',
                        'Fim ProduÃ§Ã£o SOS': '#d4edda',
                        'Tempo Acerto SOS': '#d4edda',
                        'Tempo ProduÃ§Ã£o SOS': '#d4edda',
                    }
                    
                    # Formatar cabeÃ§alho com cores
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
                    
                    # Aplicar formatos por coluna e ajustar largura (evitar len() em float)
                    for i, col in enumerate(df.columns):
                        s = df[col].apply(lambda x: str(x) if pd.notna(x) else '')
                        width = max(int(s.str.len().max()) if len(s) > 0 else 0, len(col)) + 2
                        if col in ['Refugo Porcentagem SOS', 'Refugo Porcentagem Impressora', '% EficiÃªncia']:
                            ws.set_column(i, i, width, fmt_percent)
                        elif col in numeric_cols:
                            ws.set_column(i, i, width, fmt_number)
                        elif col in ['Tempo Acerto SOS', 'Tempo ProduÃ§Ã£o SOS', 'Tempo Acerto Impressora', 'Tempo ProduÃ§Ã£o Impressora']:
                            ws.set_column(i, i, width, fmt_time)
                        elif col in ['Data SOS', 'Data Impressora', 'Data InspeÃ§Ã£o', 'Data RobÃ´']:
                            ws.set_column(i, i, width, fmt_date)
                        else:
                            ws.set_column(i, i, width)
            output.seek(0)
            return send_file(output, download_name="historico_producao.xlsx", as_attachment=True)
        except Exception as e:
            flash(f"Erro ao exportar: {e}", "danger"); return redirect(url_for('main.historico'))
    contexto = dict(
        lancamentos=lancamentos, all_operadores=ALL_OPERADORES,
        preserved_args=preserved_args, pagination_args=pagination_args, action_url=url_for('main.historico'),
        page=page, total_paginas=total_paginas, total_registros=total_registros, per_page=PER_PAGE
    )
    # Requisição feita via htmx (filtro/ordenação/paginação): devolve só o
    # fragmento de resultado, evitando reload completo da página (Fase 4 da
    # auditoria de otimização).
    if request.headers.get('HX-Request') == 'true':
        return render_template('partials/historico_resultado.html', **contexto)
    return render_template('historico.html', **contexto)

# Rota para exibir pedidos importados do CSV Sisplan
