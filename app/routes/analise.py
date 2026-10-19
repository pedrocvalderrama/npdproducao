"""Rotas de análise: Comparativo Mensal (com gráfico) e Análise por operador/máquina."""
from flask import render_template, request, flash, send_file, redirect, url_for, session, jsonify
from datetime import datetime
import pandas as pd
from io import BytesIO
from ..models import get_db_connection, inicializar_banco
from ..business import calcular_metricas_producao, calc_tempo_producao_impressora, enrich_lancamento_observacoes, get_seconds_from_time, observacoes_from_form
from ..config import ALL_OPERADORES, ALL_MAQUINAS, MAQUINAS_SOS, OPERADORES_SOS, OPERADORES_IMPRESSORA, OPERADORES_ROBO
from ..services.formato_service import obter_formato_to_largura, normalizar_descricao
from ..utils import safe_get_int, safe_get_float, safe_get_str
from . import main_bp

def _exportar_comparativo_mensal_excel(section, ano, dados):
    """Gera arquivo Excel para uma seção do comparativo mensal."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        fmt_header = workbook.add_format({
            'bold': True, 'bg_color': '#366092', 'font_color': '#FFFFFF',
            'align': 'center', 'border': 1, 'valign': 'vcenter'
        })
        fmt_number = workbook.add_format({'num_format': '#,##0'})
        fmt_number2 = workbook.add_format({'num_format': '#,##0.00'})
        fmt_percent = workbook.add_format({'num_format': '0.00%'})

        def _write_sheet(df, sheet_name, col_formats):
            if df.empty:
                df = pd.DataFrame(columns=list(col_formats.keys()))
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            ws = writer.sheets[sheet_name]
            for i, col in enumerate(df.columns):
                ws.write(0, i, col, fmt_header)
                s = df[col].apply(lambda x: str(x) if pd.notna(x) else '')
                width = max(int(s.str.len().max()) if len(s) > 0 else 0, len(str(col))) + 2
                ws.set_column(i, i, width, col_formats.get(col))

        if section == 'metricas':
            rows = []
            for r in dados['rows_mensal']:
                rows.append({
                    'Meses': r['mes_nome'],
                    'Quantidade Mês': r['quantidade_mes'],
                    'Meta Alcançada': (r['meta_alcancada'] / 100) if r.get('meta_alcancada') is not None else None,
                    'Percentual de Refugo SOS': (r['pct_refugo_sos'] / 100) if r.get('pct_refugo_sos') is not None else None,
                    'Percentual de Refugo SOS + Flexo': (r['pct_refugo_sos_flexo'] / 100) if r.get('pct_refugo_sos_flexo') is not None else None,
                })
            rows.append({
                'Meses': 'Total Geral',
                'Quantidade Mês': dados['total_quant'],
                'Meta Alcançada': (dados['total_meta_pct'] / 100) if dados.get('total_meta_pct') is not None else None,
                'Percentual de Refugo SOS': (dados['total_pct_sos'] / 100) if dados.get('total_pct_sos') is not None else None,
                'Percentual de Refugo SOS + Flexo': (dados['total_pct_sos_flexo'] / 100) if dados.get('total_pct_sos_flexo') is not None else None,
            })
            df_exp = pd.DataFrame(rows)
            _write_sheet(df_exp, 'Metricas', {
                'Meses': None,
                'Quantidade Mês': fmt_number,
                'Meta Alcançada': fmt_percent,
                'Percentual de Refugo SOS': fmt_percent,
                'Percentual de Refugo SOS + Flexo': fmt_percent,
            })
            filename = f'comparativo_metricas_{ano}.xlsx'

        elif section == 'producao_tipo':
            rows = []
            for r in dados['rows_producao_tipo']:
                rows.append({
                    'Meses': r['mes_nome'],
                    'Consumo Total': r['consumo_total'] if r['consumo_total'] > 0 else None,
                    'Refugo Produção Total (kg)': r['refugo_producao_total_kg'] if r['refugo_producao_total_kg'] > 0 else None,
                    'Percentual Produção SOS': (r['pct_producao_sos'] / 100) if r.get('pct_producao_sos') is not None else None,
                    'Percentual Produção Pré-Impresso': (r['pct_producao_pre_impresso'] / 100) if r.get('pct_producao_pre_impresso') is not None else None,
                })
            rows.append({
                'Meses': 'Total Geral',
                'Consumo Total': dados['total_consumo_total'] if dados['total_consumo_total'] > 0 else None,
                'Refugo Produção Total (kg)': dados['total_refugo_producao_total_kg'] if dados['total_refugo_producao_total_kg'] > 0 else None,
                'Percentual Produção SOS': (dados['total_pct_producao_sos'] / 100) if dados.get('total_pct_producao_sos') is not None else None,
                'Percentual Produção Pré-Impresso': (dados['total_pct_producao_pre_impresso'] / 100) if dados.get('total_pct_producao_pre_impresso') is not None else None,
            })
            df_exp = pd.DataFrame(rows)
            _write_sheet(df_exp, 'Producao Tipo', {
                'Meses': None,
                'Consumo Total': fmt_number2,
                'Refugo Produção Total (kg)': fmt_number2,
                'Percentual Produção SOS': fmt_percent,
                'Percentual Produção Pré-Impresso': fmt_percent,
            })
            filename = f'comparativo_producao_tipo_{ano}.xlsx'

        elif section == 'bobina':
            meses_cols = list(dados['meses_nome_bobina'])
            rows = []
            for grupo in dados['rows_bobina']:
                for idx, lin in enumerate(grupo['larguras']):
                    row = {
                        'BOBINAS': grupo['papel'] if idx == 0 else '',
                        'Largura': lin['largura'],
                    }
                    for mes_num, mes_nome in enumerate(meses_cols, start=1):
                        val = lin['consumo_por_mes'].get(mes_num, 0)
                        row[mes_nome] = val if val > 0 else None
                    row['Total'] = lin['total'] if lin['total'] > 0 else None
                    rows.append(row)
            if dados['rows_bobina']:
                total_row = {'BOBINAS': 'Total Geral', 'Largura': None}
                for mes_num, mes_nome in enumerate(meses_cols, start=1):
                    val = dados['totais_bobina_por_mes'].get(mes_num, 0)
                    total_row[mes_nome] = val if val > 0 else None
                total_row['Total'] = dados['total_geral_bobina'] if dados['total_geral_bobina'] > 0 else None
                rows.append(total_row)
            df_exp = pd.DataFrame(rows)
            col_formats = {'BOBINAS': None, 'Largura': fmt_number, 'Total': fmt_number2}
            for mes_nome in meses_cols:
                col_formats[mes_nome] = fmt_number2
            _write_sheet(df_exp, 'Consumo Bobina', col_formats)
            filename = f'comparativo_consumo_bobina_{ano}.xlsx'

        elif section == 'consumo_papel':
            papeis = dados['papeis_ordenados']
            rows = []
            for r in dados['rows_consumo_papel']:
                row = {'Meses': r['mes_nome']}
                for p in papeis:
                    val = r['consumo_por_papel'].get(p, 0)
                    row[p] = val if val > 0 else None
                row['Consumo Total'] = r['consumo_total_mes'] if r['consumo_total_mes'] > 0 else None
                rows.append(row)
            if papeis:
                total_row = {'Meses': 'Total Geral'}
                for p in papeis:
                    val = dados['totais_consumo_papel'].get(p, 0)
                    total_row[p] = val if val > 0 else None
                total_row['Consumo Total'] = dados['total_geral_papel'] if dados['total_geral_papel'] > 0 else None
                rows.append(total_row)
            df_exp = pd.DataFrame(rows)
            col_formats = {'Meses': None, 'Consumo Total': fmt_number2}
            for p in papeis:
                col_formats[p] = fmt_number2
            _write_sheet(df_exp, 'Consumo Papel', col_formats)
            filename = f'comparativo_consumo_papel_{ano}.xlsx'

        else:
            raise ValueError(f'Seção de exportação inválida: {section}')

    output.seek(0)
    return output, filename

# Comparativo Mensal: métricas mês a mês (Quantidade SOS, Meta Alcançada, % Refugo SOS, % Refugo SOS+Flexo)
@main_bp.route("/comparativo-mensal", methods=["GET", "POST"])
def comparativo_mensal():
    from datetime import datetime
    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT id, data, quantidade, quantidade_impressora, milheiro, refugo_acerto_sos, "
        "refugo_pre_impresso, refugo_sos, refugo_producao_total, refugo_pct, tipo_impressao, "
        "consumo_total, perdas_geral_kg, papel, formato FROM producao",
        conn,
    )
    
    # Processar salvamento de metas mensais (POST)
    if request.method == "POST":
        ano_meta = request.form.get("ano_meta")
        if ano_meta:
            try:
                ano_meta = int(ano_meta)
                cursor = conn.cursor()
                for mes in range(1, 13):
                    meta_key = f"meta_mes_{mes}"
                    meta_val = request.form.get(meta_key, "").strip().replace(".", "").replace(",", ".")
                    if meta_val:
                        try:
                            meta_quantidade = float(meta_val)
                            if meta_quantidade > 0:
                                cursor.execute("""
                                    INSERT OR REPLACE INTO metas_mensais (ano, mes, meta_quantidade)
                                    VALUES (?, ?, ?)
                                """, (ano_meta, mes, meta_quantidade))
                        except (ValueError, TypeError):
                            pass
                conn.commit()
                conn.close()
                # Redirecionar após salvar para mostrar dados atualizados
                return redirect(url_for("main.comparativo_mensal", ano=ano_meta))
            except (ValueError, TypeError):
                pass
    
    conn.close()

    # Meta padrão (para compatibilidade com código antigo)
    meta_quantidade_padrao = 1000000.0
    try:
        m = request.args.get("meta_quantidade", "1000000").strip().replace(".", "").replace(",", ".")
        if m:
            meta_quantidade_padrao = float(m)
    except (ValueError, TypeError):
        pass
    if meta_quantidade_padrao <= 0:
        meta_quantidade_padrao = 1000000.0

    MESES_NOME = (
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    )

    rows_mensal = []
    ano_used = None
    df_ano = None
    metas_dict = {}  # Inicializar metas_dict antes do bloco
    if not df.empty:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df[df["data"].notna()]
        if not df.empty:
            # Mesma lógica do histórico / lançamento de custo (não usa o valor antigo gravado):
            # consumo_util = (Quantidade SOS / 1000) × milheiro
            # consumo_total = consumo_util + perdas_geral_kg
            qtd = df["quantidade"].fillna(0).astype(float)
            mil = df["milheiro"].fillna(0).astype(float)
            perdas = df["perdas_geral_kg"].fillna(0).astype(float) if "perdas_geral_kg" in df.columns else 0.0
            df["consumo_total"] = (qtd / 1000.0) * mil + perdas

            df["mes"] = df["data"].dt.month
            df["ano"] = df["data"].dt.year.astype(int)
            df_ano = df.copy()
            # Definir ano: da URL ou o maior ano presente nos dados (evita misturar anos)
            ano_filtro = (request.args.get("ano") or "").strip()
            if ano_filtro:
                try:
                    ano_used = int(ano_filtro)
                except ValueError:
                    ano_used = None
            if ano_used is None and not df["ano"].empty:
                ano_used = int(df["ano"].max())
            # Sempre filtrar por ano antes de agregar (só conta data SOS no ano escolhido)
            if ano_used is not None:
                df = df.loc[df["ano"] == ano_used].copy()

            # Carregar metas mensais do banco de dados
            if ano_used is not None:
                conn_meta = get_db_connection()
                cursor_meta = conn_meta.cursor()
                cursor_meta.execute("SELECT mes, meta_quantidade FROM metas_mensais WHERE ano = ?", (ano_used,))
                for row in cursor_meta.fetchall():
                    metas_dict[row["mes"]] = row["meta_quantidade"]
                conn_meta.close()
            df["rsos_kg"] = (df["refugo_acerto_sos"].fillna(0) + df["refugo_pre_impresso"].fillna(0) + df["refugo_sos"].fillna(0))
            df["peso_boas_sos"] = df["quantidade"].fillna(0) * (df["milheiro"].fillna(0) / 1000)
            df["refugo_total_kg"] = df["refugo_producao_total"].fillna(0)
            df["peso_boas_total"] = (df["quantidade"].fillna(0) + df["quantidade_impressora"].fillna(0)) * (df["milheiro"].fillna(0) / 1000)

            for mes in range(1, 13):
                # Considerar só registros do ano selecionado E do mês (evita “vazar” outros anos)
                dm = df[(df["ano"] == ano_used) & (df["mes"] == mes)] if ano_used is not None else df[df["mes"] == mes]
                meta_mes = metas_dict.get(mes, meta_quantidade_padrao)
                if dm.empty:
                    rows_mensal.append({
                        "mes_num": mes,
                        "mes_nome": MESES_NOME[mes - 1],
                        "quantidade_mes": 0,
                        "meta_alcancada": 0.0,
                        "meta_quantidade": meta_mes,
                        "pct_refugo_sos": None,
                        "pct_refugo_sos_flexo": None,
                    })
                    continue
                quant_mes = int(dm["quantidade"].sum())
                soma_rsos = dm["rsos_kg"].sum()
                soma_peso_sos = dm["peso_boas_sos"].sum()
                den_sos = soma_peso_sos + soma_rsos
                pct_sos = (soma_rsos / den_sos * 100) if den_sos > 0 else None
                soma_refugo_total = dm["refugo_total_kg"].sum()
                den_sos_flexo = soma_peso_sos + soma_refugo_total
                pct_sos_flexo = (soma_refugo_total / den_sos_flexo * 100) if den_sos_flexo > 0 else None

                meta_pct = (quant_mes / meta_mes * 100) if meta_mes > 0 else 0.0

                rows_mensal.append({
                    "mes_num": mes,
                    "mes_nome": MESES_NOME[mes - 1],
                    "quantidade_mes": quant_mes,
                    "meta_alcancada": meta_pct,
                    "meta_quantidade": meta_mes,
                    "pct_refugo_sos": pct_sos,
                    "pct_refugo_sos_flexo": pct_sos_flexo,
                })

    if len(rows_mensal) < 12:
        existentes = {r["mes_num"] for r in rows_mensal}
        for mes in range(1, 13):
            if mes not in existentes:
                meta_mes = metas_dict.get(mes, meta_quantidade_padrao)
                rows_mensal.append({
                    "mes_num": mes,
                    "mes_nome": MESES_NOME[mes - 1],
                    "quantidade_mes": 0,
                    "meta_alcancada": 0.0,
                    "meta_quantidade": meta_mes,
                    "pct_refugo_sos": None,
                    "pct_refugo_sos_flexo": None,
                })
        rows_mensal.sort(key=lambda x: x["mes_num"])

    # Total geral
    total_quant = sum(r["quantidade_mes"] for r in rows_mensal)
    # Meta Alcançada: média das metas alcançadas (não soma das porcentagens)
    meta_alcancadas = [r["meta_alcancada"] for r in rows_mensal if r.get("meta_alcancada") is not None]
    total_meta_pct = sum(meta_alcancadas) / len(meta_alcancadas) if meta_alcancadas else None
    # Refugo SOS: percentual consolidado do período (refugo_sos / (peso_boas_sos + refugo_sos) × 100)
    total_pct_sos = None
    total_pct_sos_flexo = None
    if not df.empty and "rsos_kg" in df.columns:
        soma_rsos_g = df["rsos_kg"].sum()
        soma_peso_sos_g = df["peso_boas_sos"].sum()
        den_g = soma_peso_sos_g + soma_rsos_g
        total_pct_sos = (soma_rsos_g / den_g * 100) if den_g > 0 else None
        soma_rt_g = df["refugo_total_kg"].sum()
        den_tg_sos = soma_peso_sos_g + soma_rt_g
        total_pct_sos_flexo = (soma_rt_g / den_tg_sos * 100) if den_tg_sos > 0 else None

    anos_disponiveis = [datetime.now().year]
    if df_ano is not None and not df_ano.empty and "ano" in df_ano.columns:
        anos_disponiveis = sorted(df_ano["ano"].dropna().unique().astype(int).tolist(), reverse=True)
    ano_selecionado = request.args.get("ano")
    if not ano_selecionado:
        ano_selecionado = str(ano_used) if ano_used is not None else str(anos_disponiveis[0])
    
    # Garantir que ano_used esteja definido mesmo sem dados
    if ano_used is None:
        try:
            ano_used = int(ano_selecionado)
        except (ValueError, TypeError):
            ano_used = datetime.now().year
    
    # Carregar metas mensais se ainda não carregadas (quando não há dados no df)
    if ano_used is not None and not metas_dict:
        conn_meta = get_db_connection()
        cursor_meta = conn_meta.cursor()
        cursor_meta.execute("SELECT mes, meta_quantidade FROM metas_mensais WHERE ano = ?", (ano_used,))
        for row in cursor_meta.fetchall():
            metas_dict[row["mes"]] = row["meta_quantidade"]
        conn_meta.close()

    for r in rows_mensal:
        r["quantidade_mes_fmt"] = f"{r['quantidade_mes']:,}".replace(",", ".")
        r["meta_alcancada_fmt"] = f"{r['meta_alcancada']:.2f}".replace(".", ",") + "%" if r["meta_alcancada"] is not None else "—"
        r["pct_refugo_sos_fmt"] = f"{r['pct_refugo_sos']:.2f}".replace(".", ",") + "%" if r.get("pct_refugo_sos") is not None else "—"
        r["pct_refugo_sos_flexo_fmt"] = f"{r['pct_refugo_sos_flexo']:.2f}".replace(".", ",") + "%" if r.get("pct_refugo_sos_flexo") is not None else "—"
    total_quantidade_fmt = f"{total_quant:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    total_meta_fmt = f"{total_meta_pct:.2f}".replace(".", ",") + "%" if total_meta_pct is not None else "—"
    total_pct_sos_fmt = f"{total_pct_sos:.2f}".replace(".", ",") + "%" if total_pct_sos is not None else "—"
    total_pct_sos_flexo_fmt = f"{total_pct_sos_flexo:.2f}".replace(".", ",") + "%" if total_pct_sos_flexo is not None else "—"

    # Preparar dados para a segunda tabela (Consumo e Produção por Tipo)
    rows_producao_tipo = []
    
    # Processar dados mensais para a segunda tabela
    for mes in range(1, 13):
        if not df.empty and ano_used is not None:
            dm = df[(df["ano"] == ano_used) & (df["mes"] == mes)]
        else:
            dm = pd.DataFrame()
        
        if dm.empty:
            rows_producao_tipo.append({
                "mes_num": mes,
                "mes_nome": MESES_NOME[mes - 1],
                "consumo_total": 0,
                "refugo_producao_total_kg": 0,
                "pct_producao_sos": None,
                "pct_producao_pre_impresso": None,
            })
            continue
        
        # Consumo Total
        consumo_total = dm["consumo_total"].fillna(0).sum() if "consumo_total" in dm.columns else 0
        
        # Refugo Produção Total (kg)
        refugo_producao_total_kg = dm["refugo_producao_total"].fillna(0).sum() if "refugo_producao_total" in dm.columns else 0
        
        # Quantidade total produzida do mês (apenas SOS, campo "quantidade")
        # O tipo_impressao se refere apenas à produção SOS, então usamos apenas "quantidade" como base
        quantidade_total = 0
        if "quantidade" in dm.columns:
            quantidade_total = dm["quantidade"].fillna(0).sum()
        
        # Quantidade por tipo de impressão (baseado na produção SOS, campo "quantidade")
        quantidade_sos = 0
        quantidade_pre_impresso = 0
        
        if "tipo_impressao" in dm.columns and "quantidade" in dm.columns:
            dm_tipo = dm.copy()
            dm_tipo["tipo_impressao"] = dm_tipo["tipo_impressao"].fillna("").str.strip()
            # Quantidade produzida como SOS (tipo_impressao = "SOS")
            quantidade_sos = dm_tipo[dm_tipo["tipo_impressao"].str.upper() == "SOS"]["quantidade"].fillna(0).sum()
            # Quantidade produzida como Pré-Impresso (tipo_impressao = "Pré-Impresso")
            mask_pre_impresso = dm_tipo["tipo_impressao"].str.upper().isin(["PRÉ-IMPRESSO", "PRE-IMPRESSO", "PRÉ IMPRESSO", "PRE IMPRESSO"])
            quantidade_pre_impresso = dm_tipo[mask_pre_impresso]["quantidade"].fillna(0).sum()
        
        # Percentuais em relação à quantidade total do mês (quantidade SOS)
        # A soma dos dois percentuais deve dar 100% (ou próximo, se houver valores sem tipo definido)
        pct_producao_sos = (quantidade_sos / quantidade_total * 100) if quantidade_total > 0 else None
        pct_producao_pre_impresso = (quantidade_pre_impresso / quantidade_total * 100) if quantidade_total > 0 else None
        
        rows_producao_tipo.append({
            "mes_num": mes,
            "mes_nome": MESES_NOME[mes - 1],
            "consumo_total": consumo_total,
            "refugo_producao_total_kg": refugo_producao_total_kg,
            "pct_producao_sos": pct_producao_sos,
            "pct_producao_pre_impresso": pct_producao_pre_impresso,
        })
    
    # Formatar valores da segunda tabela
    for r in rows_producao_tipo:
        r["consumo_total_fmt"] = f"{r['consumo_total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if r["consumo_total"] > 0 else "—"
        r["refugo_producao_total_kg_fmt"] = f"{r['refugo_producao_total_kg']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if r["refugo_producao_total_kg"] > 0 else "—"
        r["pct_producao_sos_fmt"] = f"{r['pct_producao_sos']:.2f}".replace(".", ",") + "%" if r.get("pct_producao_sos") is not None else "—"
        r["pct_producao_pre_impresso_fmt"] = f"{r['pct_producao_pre_impresso']:.2f}".replace(".", ",") + "%" if r.get("pct_producao_pre_impresso") is not None else "—"
    
    # Consumo Total por Tipo de Papel (agrupamento do Consumo Total por coluna Papel)
    papeis_ordenados = []
    rows_consumo_papel = []
    totais_consumo_papel = {}
    if not df.empty and "papel" in df.columns and "consumo_total" in df.columns and ano_used is not None:
        df["papel"] = df["papel"].fillna("Não informado").astype(str).str.strip()
        papeis_ordenados = sorted(df["papel"].unique().tolist())
        totais_consumo_papel = {p: 0.0 for p in papeis_ordenados}
        for mes in range(1, 13):
            dm = df[(df["ano"] == ano_used) & (df["mes"] == mes)]
            consumo_por_papel = {}
            for p in papeis_ordenados:
                val = dm[dm["papel"] == p]["consumo_total"].fillna(0).sum() if not dm.empty else 0.0
                consumo_por_papel[p] = val
                totais_consumo_papel[p] = totais_consumo_papel.get(p, 0) + val
            total_mes = sum(consumo_por_papel.values())
            rows_consumo_papel.append({
                "mes_num": mes,
                "mes_nome": MESES_NOME[mes - 1],
                "consumo_por_papel": consumo_por_papel,
                "consumo_total_mes": total_mes,
            })
        # Formatar valores para exibição
        for r in rows_consumo_papel:
            r["consumo_por_papel_fmt"] = {p: f"{r['consumo_por_papel'][p]:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if r["consumo_por_papel"][p] > 0 else "—" for p in papeis_ordenados}
            r["consumo_total_mes_fmt"] = f"{r['consumo_total_mes']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if r["consumo_total_mes"] > 0 else "—"
        totais_consumo_papel_fmt = {p: f"{totais_consumo_papel[p]:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if totais_consumo_papel.get(p, 0) > 0 else "—" for p in papeis_ordenados}
        total_geral_papel = sum(totais_consumo_papel.values())
        total_geral_papel_fmt = f"{total_geral_papel:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if total_geral_papel > 0 else "—"
    else:
        for mes in range(1, 13):
            rows_consumo_papel.append({
                "mes_num": mes,
                "mes_nome": MESES_NOME[mes - 1],
                "consumo_por_papel": {},
                "consumo_por_papel_fmt": {},
                "consumo_total_mes": 0,
                "consumo_total_mes_fmt": "—",
            })
        totais_consumo_papel_fmt = {}
        total_geral_papel_fmt = "—"
    
    # Consumo de Papel por Bobina: agrupar por Papel e por largura cadastrada
    # em formatos_cadastro (tela Configurações de formatos → Largura Bobina).
    LARGURAS_ORDER = [32, 58, 70, 80, 90, 99, 110]
    formato_to_largura = obter_formato_to_largura()
    # Inclui automaticamente larguras cadastradas que ainda não estão na ordem padrão
    for largura in sorted({int(v) for v in formato_to_largura.values() if v is not None}):
        if largura not in LARGURAS_ORDER:
            LARGURAS_ORDER.append(largura)
    PAPEIS_BOBINA_ORDER = ["BAG 100GRS", "BAG 70GRS", "BAG 80GRS", "BRANCO 110GRS"]
    rows_bobina = []
    totais_bobina_por_mes = {mes: 0.0 for mes in range(1, 13)}
    total_geral_bobina = 0.0
    if not df.empty and ano_used is not None and "papel" in df.columns and "formato" in df.columns and "consumo_total" in df.columns:
        df_b = df[df["ano"] == ano_used].copy()
        df_b["papel"] = df_b["papel"].fillna("").astype(str).str.strip()
        df_b["formato"] = df_b["formato"].fillna("").astype(str).map(normalizar_descricao)
        df_b["largura"] = df_b["formato"].map(lambda f: formato_to_largura.get(f, None))
        df_b = df_b[df_b["largura"].notna()]
        df_b["papel_display"] = df_b["papel"].replace({"BRANCO 110G": "BRANCO 110GRS"})
        papeis_presentes = df_b["papel_display"].unique().tolist()
        papeis_bobina_order = [p for p in PAPEIS_BOBINA_ORDER if p in papeis_presentes]
        for p in papeis_presentes:
            if p not in papeis_bobina_order:
                papeis_bobina_order.append(p)
        for papel in papeis_bobina_order:
            df_p = df_b[df_b["papel_display"] == papel]
            larguras_presentes = sorted(df_p["largura"].dropna().unique().astype(int).tolist())
            larguras_presentes = [l for l in LARGURAS_ORDER if l in larguras_presentes]
            if not larguras_presentes:
                larguras_presentes = sorted(df_p["largura"].dropna().unique().astype(int).tolist())
            linhas_papel = []
            for largura in larguras_presentes:
                df_pl = df_p[df_p["largura"] == largura]
                consumo_por_mes = {}
                total_linha = 0.0
                for mes in range(1, 13):
                    dm = df_pl[df_pl["mes"] == mes]
                    val = dm["consumo_total"].fillna(0).sum() if not dm.empty else 0.0
                    consumo_por_mes[mes] = val
                    total_linha += val
                    totais_bobina_por_mes[mes] = totais_bobina_por_mes.get(mes, 0) + val
                total_geral_bobina += total_linha
                consumo_por_mes_fmt = {mes: f"{consumo_por_mes[mes]:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if consumo_por_mes[mes] > 0 else "—" for mes in range(1, 13)}
                total_linha_fmt = f"{total_linha:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if total_linha > 0 else "—"
                linhas_papel.append({
                    "largura": largura,
                    "consumo_por_mes": consumo_por_mes,
                    "consumo_por_mes_fmt": consumo_por_mes_fmt,
                    "total": total_linha,
                    "total_fmt": total_linha_fmt,
                })
            rows_bobina.append({"papel": papel, "larguras": linhas_papel})
    totais_bobina_por_mes_fmt = {mes: f"{totais_bobina_por_mes[mes]:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if totais_bobina_por_mes.get(mes, 0) > 0 else "—" for mes in range(1, 13)}
    total_geral_bobina_fmt = f"{total_geral_bobina:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if total_geral_bobina > 0 else "—"
    MESES_NOME_BOBINA = ("JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO")
    
    # Totais da segunda tabela
    total_consumo_total = sum(r["consumo_total"] for r in rows_producao_tipo)
    total_refugo_producao_total_kg = sum(r["refugo_producao_total_kg"] for r in rows_producao_tipo)
    
    # Calcular percentuais totais (consolidado do ano)
    if not df.empty and ano_used is not None and "tipo_impressao" in df.columns:
        df_ano_filtrado = df[df["ano"] == ano_used] if ano_used is not None else df
        df_ano_filtrado_tipo = df_ano_filtrado.copy()
        df_ano_filtrado_tipo["tipo_impressao"] = df_ano_filtrado_tipo["tipo_impressao"].fillna("").str.strip()
        
        if "quantidade" in df_ano_filtrado.columns:
            # Quantidade total do ano (apenas SOS, campo "quantidade")
            quantidade_total_geral = df_ano_filtrado["quantidade"].fillna(0).sum()
            # Quantidade produzida como SOS no ano
            quantidade_sos_geral = df_ano_filtrado_tipo[df_ano_filtrado_tipo["tipo_impressao"].str.upper() == "SOS"]["quantidade"].fillna(0).sum()
            # Quantidade produzida como Pré-Impresso no ano
            mask_pre_impresso_geral = df_ano_filtrado_tipo["tipo_impressao"].str.upper().isin(["PRÉ-IMPRESSO", "PRE-IMPRESSO", "PRÉ IMPRESSO", "PRE IMPRESSO"])
            quantidade_pre_impresso_geral = df_ano_filtrado_tipo[mask_pre_impresso_geral]["quantidade"].fillna(0).sum()
            
            # Percentuais em relação à quantidade total do ano (quantidade SOS)
            # A soma dos dois percentuais deve dar 100% (ou próximo, se houver valores sem tipo definido)
            total_pct_producao_sos = (quantidade_sos_geral / quantidade_total_geral * 100) if quantidade_total_geral > 0 else None
            total_pct_producao_pre_impresso = (quantidade_pre_impresso_geral / quantidade_total_geral * 100) if quantidade_total_geral > 0 else None
        else:
            total_pct_producao_sos = None
            total_pct_producao_pre_impresso = None
    else:
        total_pct_producao_sos = None
        total_pct_producao_pre_impresso = None
    
    total_consumo_total_fmt = f"{total_consumo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if total_consumo_total > 0 else "—"
    total_refugo_producao_total_kg_fmt = f"{total_refugo_producao_total_kg:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if total_refugo_producao_total_kg > 0 else "—"
    total_pct_producao_sos_fmt = f"{total_pct_producao_sos:.2f}".replace(".", ",") + "%" if total_pct_producao_sos is not None else "—"
    total_pct_producao_pre_impresso_fmt = f"{total_pct_producao_pre_impresso:.2f}".replace(".", ",") + "%" if total_pct_producao_pre_impresso is not None else "—"

    # Dados para o gráfico comparativo mensal (renderizado no navegador com
    # Chart.js — Fase 4 da auditoria de otimização — em vez de gerar uma
    # imagem PNG no servidor com matplotlib).
    chart_data = None
    if rows_mensal:
        quantidades_chart = [r['quantidade_mes'] for r in rows_mensal]
        pct_sos_chart = [r.get('pct_refugo_sos') for r in rows_mensal]
        pct_sos_flexo_chart = [r.get('pct_refugo_sos_flexo') for r in rows_mensal]
        tem_dados = (
            any(q != 0 for q in quantidades_chart)
            or any(p not in (None, 0) for p in pct_sos_chart)
            or any(p not in (None, 0) for p in pct_sos_flexo_chart)
        )
        if tem_dados:
            chart_data = {
                'meses': [r['mes_nome'] for r in rows_mensal],
                'quantidades': quantidades_chart,
                'pct_refugo_sos': pct_sos_chart,
                'pct_refugo_sos_flexo': pct_sos_flexo_chart,
            }

    export_section = request.args.get("section", "").strip()
    if request.args.get("export") == "excel" and export_section:
        try:
            export_dados = {
                'rows_mensal': rows_mensal,
                'total_quant': total_quant,
                'total_meta_pct': total_meta_pct,
                'total_pct_sos': total_pct_sos,
                'total_pct_sos_flexo': total_pct_sos_flexo,
                'rows_producao_tipo': rows_producao_tipo,
                'total_consumo_total': total_consumo_total,
                'total_refugo_producao_total_kg': total_refugo_producao_total_kg,
                'total_pct_producao_sos': total_pct_producao_sos,
                'total_pct_producao_pre_impresso': total_pct_producao_pre_impresso,
                'rows_bobina': rows_bobina,
                'meses_nome_bobina': MESES_NOME_BOBINA,
                'totais_bobina_por_mes': totais_bobina_por_mes,
                'total_geral_bobina': total_geral_bobina,
                'rows_consumo_papel': rows_consumo_papel,
                'papeis_ordenados': papeis_ordenados,
                'totais_consumo_papel': totais_consumo_papel if papeis_ordenados else {},
                'total_geral_papel': sum(totais_consumo_papel.values()) if papeis_ordenados else 0,
            }
            output, filename = _exportar_comparativo_mensal_excel(export_section, ano_selecionado, export_dados)
            return send_file(output, download_name=filename, as_attachment=True)
        except Exception as e:
            flash(f"Erro ao exportar: {e}", "danger")
            return redirect(url_for("main.comparativo_mensal", ano=ano_selecionado))

    return render_template(
        "comparativo_mensal.html",
        rows_mensal=rows_mensal,
        meta_quantidade=int(meta_quantidade_padrao),
        total_quantidade_fmt=total_quantidade_fmt,
        total_meta_fmt=total_meta_fmt,
        total_pct_sos_fmt=total_pct_sos_fmt,
        total_pct_sos_flexo_fmt=total_pct_sos_flexo_fmt,
        rows_producao_tipo=rows_producao_tipo,
        total_consumo_total_fmt=total_consumo_total_fmt,
        total_refugo_producao_total_kg_fmt=total_refugo_producao_total_kg_fmt,
        total_pct_producao_sos_fmt=total_pct_producao_sos_fmt,
        total_pct_producao_pre_impresso_fmt=total_pct_producao_pre_impresso_fmt,
        papeis_ordenados=papeis_ordenados,
        rows_consumo_papel=rows_consumo_papel,
        totais_consumo_papel_fmt=totais_consumo_papel_fmt,
        total_geral_papel_fmt=total_geral_papel_fmt,
        chart_data=chart_data,
        rows_bobina=rows_bobina,
        totais_bobina_por_mes_fmt=totais_bobina_por_mes_fmt,
        total_geral_bobina_fmt=total_geral_bobina_fmt,
        meses_nome_bobina=MESES_NOME_BOBINA,
        anos_disponiveis=anos_disponiveis,
        ano_selecionado=ano_selecionado,
        action_url=url_for("main.comparativo_mensal"),
    )

def _time_str_to_excel_fraction(time_str):
    if not time_str or pd.isna(time_str) or str(time_str) == "00:00:00":
        return None
    parts = str(time_str).split(':')
    try:
        h, m = int(parts[0]), int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
        return (h * 3600 + m * 60 + s) / 86400.0
    except (ValueError, IndexError):
        return None

def _exportar_analise_excel(section, summary, total):
    """Gera arquivo Excel para uma seção da página de análise."""
    section_config = {
        'sos': {
            'sheet': 'Analise SOS',
            'filename': 'analise_sos.xlsx',
            'columns': [
                ('sos', 'SOS'),
                ('media_sacos_p_min', 'Média de Sacos p/ Min', 'number2'),
                ('contagem_servico', 'Contagem de Serviços', 'number'),
                ('media_percentual_refugo', 'Média de Refugo', 'percent'),
                ('soma_quant', 'Soma de Quantidade SOS', 'number'),
                ('media_tempo_acerto', 'Média de Acerto', 'time'),
            ],
            'label_key': 'sos',
        },
        'impressora': {
            'sheet': 'Analise Impressora',
            'filename': 'analise_impressora.xlsx',
            'columns': [
                ('impressora', 'Impressora'),
                ('media_sacos_p_min', 'Média de Sacos p/ Min', 'number2'),
                ('contagem_servico', 'Contagem de Serviços', 'number'),
                ('media_percentual_refugo', 'Média de Refugo', 'percent'),
                ('soma_quant', 'Soma de Quantidade Impressora', 'number'),
                ('media_tempo_acerto', 'Média de Acerto', 'time'),
            ],
            'label_key': 'impressora',
        },
        'robo': {
            'sheet': 'Analise Robo',
            'filename': 'analise_robo.xlsx',
            'columns': [
                ('robo', 'Robô'),
                ('contagem_servico', 'Contagem de Serviços', 'number'),
                ('refugo_pecas', 'Refugo Peças', 'number'),
                ('soma_quantidade_robo', 'Soma da Quantidade Robô', 'number'),
            ],
            'label_key': 'robo',
        },
        'operator_sos': {
            'sheet': 'Analise Operador SOS',
            'filename': 'analise_operador_sos.xlsx',
            'columns': [
                ('operador', 'Operador'),
                ('media_sacos_p_min', 'Média de Sacos p/ Min', 'number2'),
                ('contagem_servico', 'Contagem de Serviços', 'number'),
                ('media_percentual_refugo', 'Média de Refugo', 'percent'),
                ('media_total_acerto', 'Média de Acerto', 'time'),
            ],
            'label_key': 'operador',
        },
        'operator_impressora': {
            'sheet': 'Analise Operador Impressora',
            'filename': 'analise_operador_impressora.xlsx',
            'columns': [
                ('operador', 'Operador'),
                ('media_sacos_p_min', 'Média de Sacos p/ Min', 'number2'),
                ('contagem_servico', 'Contagem de Serviços', 'number'),
                ('media_percentual_refugo', 'Média de Refugo', 'percent'),
                ('media_total_acerto', 'Média de Acerto', 'time'),
            ],
            'label_key': 'operador',
        },
    }
    if section not in section_config:
        raise ValueError(f'Seção de exportação inválida: {section}')

    cfg = section_config[section]
    summary = summary or []
    total = total or {}

    def _cell_value(key, fmt_type, row):
        val = row.get(key)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if fmt_type == 'percent':
            return float(val) / 100 if val != '' else None
        if fmt_type == 'time':
            return _time_str_to_excel_fraction(val)
        if fmt_type in ('number', 'number2'):
            try:
                return float(val)
            except (TypeError, ValueError):
                return None
        return val

    rows = []
    for item in summary:
        row = {}
        for key, label, *fmt in cfg['columns']:
            fmt_type = fmt[0] if fmt else None
            row[label] = _cell_value(key, fmt_type, item)
        rows.append(row)
    if total:
        total_row = {}
        label_key = cfg['label_key']
        for key, label, *fmt in cfg['columns']:
            fmt_type = fmt[0] if fmt else None
            if key == label_key:
                total_row[label] = total.get(key, 'Total Geral')
            else:
                total_row[label] = _cell_value(key, fmt_type, total)
        rows.append(total_row)

    col_labels = [col[1] for col in cfg['columns']]
    df_exp = pd.DataFrame(rows, columns=col_labels)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        fmt_header = workbook.add_format({
            'bold': True, 'bg_color': '#366092', 'font_color': '#FFFFFF',
            'align': 'center', 'border': 1, 'valign': 'vcenter'
        })
        fmt_number = workbook.add_format({'num_format': '#,##0'})
        fmt_number2 = workbook.add_format({'num_format': '#,##0.00'})
        fmt_percent = workbook.add_format({'num_format': '0.00%'})
        fmt_time = workbook.add_format({'num_format': '[h]:mm:ss'})
        fmt_map = {'number': fmt_number, 'number2': fmt_number2, 'percent': fmt_percent, 'time': fmt_time}

        df_exp.to_excel(writer, index=False, sheet_name=cfg['sheet'])
        ws = writer.sheets[cfg['sheet']]
        for i, (key, label, *fmt) in enumerate(cfg['columns']):
            ws.write(0, i, label, fmt_header)
            fmt_type = fmt[0] if fmt else None
            col_fmt = fmt_map.get(fmt_type)
            s = df_exp[label].apply(lambda x: str(x) if pd.notna(x) else '')
            width = max(int(s.str.len().max()) if len(s) > 0 else 0, len(label)) + 2
            ws.set_column(i, i, width, col_fmt)

    output.seek(0)
    return output, cfg['filename']

# Rota para exibir a análise detalhada em tabelas
@main_bp.route("/analise")
def analise():
    conn = get_db_connection()
    # Carrega só as colunas realmente usadas nesta tela (em vez de `SELECT *`),
    # reduzindo o tamanho do DataFrame — e das 5 cópias feitas abaixo para cada
    # trilha de análise (SOS, Impressora, Robô, Operador SOS, Operador
    # Impressora) — sem alterar nenhum cálculo/filtro existente.
    df_all = pd.read_sql_query(
        """
        SELECT id, data, data_impressora, data_robo, data_inspecao,
               servico, num_of, operador, operador_impressora, operador_robo,
               sos, robo_alca, impressora,
               quantidade, quantidade_impressora, quantidade_robo, milheiro,
               velocidade_un_min, velocidade_un_min_flexo,
               tempo_acerto_s, tempo_acerto_impressora,
               refugo_acerto_sos, refugo_pre_impresso, refugo_sos,
               refugo_flexo, refugo_acerto_flexo, refugo_robo,
               refugo_producao_total, refugo_pct, refugo_pct_flexo
        FROM producao
        """,
        conn,
    )
    conn.close()
    
    # Prepara o DataFrame original com conversões de data
    if not df_all.empty:
        df_all['data'] = pd.to_datetime(df_all['data'], errors='coerce')
        df_all['data_impressora'] = pd.to_datetime(df_all['data_impressora'], errors='coerce')
        df_all['data_robo'] = pd.to_datetime(df_all['data_robo'], errors='coerce')
        df_all['data_inspecao'] = pd.to_datetime(df_all['data_inspecao'], errors='coerce')
    
    # DataFrame específico para Análise SOS (completamente independente - começa do DataFrame original)
    df_sos_analysis = df_all.copy() if not df_all.empty else pd.DataFrame()
    if not df_sos_analysis.empty:
        # Aplica filtros específicos de SOS (apenas os que começam com 'sos_')
        sos_servico = request.args.get('sos_servico', '').strip()
        if sos_servico:
            df_sos_analysis = df_sos_analysis[df_sos_analysis['servico'].str.contains(sos_servico, case=False, na=False)]
        sos_num_of = request.args.get('sos_num_of', '').strip()
        if sos_num_of:
            df_sos_analysis = df_sos_analysis[df_sos_analysis['num_of'].str.contains(sos_num_of, case=False, na=False)]
        sos_start_date = request.args.get('sos_start_date')
        sos_end_date = request.args.get('sos_end_date')
        if sos_start_date and sos_end_date:
            df_sos_analysis = df_sos_analysis[(df_sos_analysis['data'] >= sos_start_date) & (df_sos_analysis['data'] <= sos_end_date)]
        selected_sos_operadores = request.args.getlist('sos_operadores')
        if selected_sos_operadores:
            df_sos_analysis = df_sos_analysis[df_sos_analysis['operador'].isin(selected_sos_operadores)]
        selected_sos_maquinas = request.args.getlist('sos_maquinas')
        if selected_sos_maquinas:
            df_sos_analysis = df_sos_analysis[df_sos_analysis['sos'].isin(selected_sos_maquinas)]
    
    # DataFrame específico para Análise Impressora (completamente independente - começa do DataFrame original)
    df_impressora_analysis = df_all.copy() if not df_all.empty else pd.DataFrame()
    if not df_impressora_analysis.empty:
        # Aplica filtros específicos de Impressora (apenas os que começam com 'impressora_')
        impressora_servico = request.args.get('impressora_servico', '').strip()
        if impressora_servico:
            df_impressora_analysis = df_impressora_analysis[df_impressora_analysis['servico'].str.contains(impressora_servico, case=False, na=False)]
        impressora_num_of = request.args.get('impressora_num_of', '').strip()
        if impressora_num_of:
            df_impressora_analysis = df_impressora_analysis[df_impressora_analysis['num_of'].str.contains(impressora_num_of, case=False, na=False)]
        impressora_start_date_impressora = request.args.get('impressora_start_date_impressora')
        impressora_end_date_impressora = request.args.get('impressora_end_date_impressora')
        if impressora_start_date_impressora and impressora_end_date_impressora:
            df_impressora_analysis = df_impressora_analysis[(df_impressora_analysis['data_impressora'] >= impressora_start_date_impressora) & (df_impressora_analysis['data_impressora'] <= impressora_end_date_impressora)]
        selected_impressora_operadores = request.args.getlist('impressora_operadores')
        if selected_impressora_operadores:
            df_impressora_analysis = df_impressora_analysis[df_impressora_analysis['operador_impressora'].isin(selected_impressora_operadores)]
    
    # DataFrame base para outras análises (usado apenas para operador SOS quando não há filtros específicos)
    df_base = df_sos_analysis.copy() if not df_sos_analysis.empty else pd.DataFrame()
    df_operator_impressora_final = pd.DataFrame()
    
    # DataFrame específico para Análise por Operador (completamente independente - começa do DataFrame original)
    df_operator_analysis = df_all.copy() if not df_all.empty else pd.DataFrame()
    if not df_operator_analysis.empty:
        # Aplica filtros específicos de operador (apenas os que começam com 'operator_')
        operator_servico = request.args.get('operator_servico', '').strip()
        if operator_servico:
            df_operator_analysis = df_operator_analysis[df_operator_analysis['servico'].str.contains(operator_servico, case=False, na=False)]
        operator_num_of = request.args.get('operator_num_of', '').strip()
        if operator_num_of:
            df_operator_analysis = df_operator_analysis[df_operator_analysis['num_of'].str.contains(operator_num_of, case=False, na=False)]
        operator_start_date = request.args.get('operator_start_date')
        operator_end_date = request.args.get('operator_end_date')
        if operator_start_date and operator_end_date:
            df_operator_analysis['data'] = pd.to_datetime(df_operator_analysis['data'], errors='coerce')
            df_operator_analysis = df_operator_analysis[(df_operator_analysis['data'] >= operator_start_date) & (df_operator_analysis['data'] <= operator_end_date)]
        selected_operator_operadores = request.args.getlist('operator_operadores')
        if selected_operator_operadores:
            df_operator_analysis = df_operator_analysis[df_operator_analysis['operador'].isin(selected_operator_operadores)]
        selected_operator_maquinas = request.args.getlist('operator_maquinas')
        if selected_operator_maquinas:
            df_operator_analysis = df_operator_analysis[df_operator_analysis['sos'].isin(selected_operator_maquinas)]
    
    # DataFrame específico para Análise por Operador Impressora (completamente independente - começa do DataFrame original)
    df_operator_impressora_analysis = df_all.copy() if not df_all.empty else pd.DataFrame()
    if not df_operator_impressora_analysis.empty:
        # Aplica filtros específicos de operador impressora (apenas os que começam com 'operator_impressora_')
        operator_impressora_servico = request.args.get('operator_impressora_servico', '').strip()
        if operator_impressora_servico:
            df_operator_impressora_analysis = df_operator_impressora_analysis[df_operator_impressora_analysis['servico'].str.contains(operator_impressora_servico, case=False, na=False)]
        operator_impressora_num_of = request.args.get('operator_impressora_num_of', '').strip()
        if operator_impressora_num_of:
            df_operator_impressora_analysis = df_operator_impressora_analysis[df_operator_impressora_analysis['num_of'].str.contains(operator_impressora_num_of, case=False, na=False)]
        operator_impressora_start_date_impressora = request.args.get('operator_impressora_start_date_impressora')
        operator_impressora_end_date_impressora = request.args.get('operator_impressora_end_date_impressora')
        if operator_impressora_start_date_impressora and operator_impressora_end_date_impressora:
            df_operator_impressora_analysis['data_impressora'] = pd.to_datetime(df_operator_impressora_analysis['data_impressora'], errors='coerce')
            df_operator_impressora_analysis = df_operator_impressora_analysis[(df_operator_impressora_analysis['data_impressora'] >= operator_impressora_start_date_impressora) & (df_operator_impressora_analysis['data_impressora'] <= operator_impressora_end_date_impressora)]
        selected_operator_impressora_operadores = request.args.getlist('operator_impressora_operadores')
        if selected_operator_impressora_operadores:
            df_operator_impressora_analysis = df_operator_impressora_analysis[df_operator_impressora_analysis['operador_impressora'].isin(selected_operator_impressora_operadores)]
    
    # DataFrame específico para Análise Robô (com filtros: Serviço, Nº OF, Data Robô, Operador)
    df_robo_analysis = df_all.copy() if not df_all.empty else pd.DataFrame()
    if not df_robo_analysis.empty:
        robo_servico = request.args.get('robo_servico', '').strip()
        if robo_servico:
            df_robo_analysis = df_robo_analysis[df_robo_analysis['servico'].str.contains(robo_servico, case=False, na=False)]
        robo_num_of = request.args.get('robo_num_of', '').strip()
        if robo_num_of:
            df_robo_analysis = df_robo_analysis[df_robo_analysis['num_of'].str.contains(robo_num_of, case=False, na=False)]
        robo_start_date_robo = request.args.get('robo_start_date_robo')
        robo_end_date_robo = request.args.get('robo_end_date_robo')
        if robo_start_date_robo and robo_end_date_robo:
            df_robo_analysis = df_robo_analysis[(df_robo_analysis['data_robo'] >= robo_start_date_robo) & (df_robo_analysis['data_robo'] <= robo_end_date_robo)]
        selected_robo_operadores = request.args.getlist('robo_operadores')
        if selected_robo_operadores:
            df_robo_analysis = df_robo_analysis[df_robo_analysis['operador_robo'].isin(selected_robo_operadores)]
    
    machine_summary, operator_summary, machine_total, operator_total, operator_impressora_summary, operator_impressora_total = [None] * 6
    robo_summary, robo_total = None, None
    # Inicializados aqui (e não só dentro do `if not df_sos_analysis.empty`) porque
    # são referenciados no render_template mesmo quando não há nenhum registro de
    # produção (ex.: banco recém-criado) — sem isso, a rota quebrava com
    # UnboundLocalError nesse cenário.
    impressora_summary, impressora_total = None, None
    
    # Função auxiliar para formatar segundos (definida aqui para uso em todas as análises)
    def format_seconds(seconds):
        if pd.isna(seconds) or seconds == 0: return "00:00:00"
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02}:{minutes:02}:{secs:02}"

    def calc_media_refugo_sos_consolidada(df):
        """Percentual consolidado: refugo_sos / (peso_boas_sos + refugo_sos) × 100."""
        if df is None or df.empty:
            return 0
        rsos_kg = df['refugo_acerto_sos'].fillna(0) + df['refugo_pre_impresso'].fillna(0) + df['refugo_sos'].fillna(0)
        peso_boas = df['quantidade'].fillna(0) * (df['milheiro'].fillna(0) / 1000)
        soma_rsos = rsos_kg.sum()
        den = peso_boas.sum() + soma_rsos
        if den > 0:
            return soma_rsos / den * 100
        return df['refugo_pct'].mean() if 'refugo_pct' in df.columns and not df.empty else 0

    def calc_media_refugo_flexo_consolidada(df):
        """Percentual consolidado: refugo_flexo / (peso_boas_flexo + refugo_flexo) × 100."""
        if df is None or df.empty:
            return 0
        rflexo_kg = df['refugo_flexo'].fillna(0) + df['refugo_acerto_flexo'].fillna(0) + df['refugo_pre_impresso'].fillna(0)
        peso_boas = df['quantidade_impressora'].fillna(0) * (df['milheiro'].fillna(0) / 1000)
        soma_rflexo = rflexo_kg.sum()
        den = peso_boas.sum() + soma_rflexo
        if den > 0:
            return soma_rflexo / den * 100
        return df['refugo_pct_flexo'].mean() if 'refugo_pct_flexo' in df.columns and not df.empty else 0

    def merge_refugo_consolidado(summary_df, source_df, group_col, calc_fn):
        """Substitui média simples de refugo pelo percentual consolidado por grupo."""
        if source_df is None or source_df.empty:
            return summary_df
        grouped = source_df.groupby(group_col)
        try:
            refugo = grouped.apply(calc_fn, include_groups=False).reset_index(name='media_percentual_refugo')
        except TypeError:
            refugo = grouped.apply(calc_fn).reset_index(name='media_percentual_refugo')
        if 'media_percentual_refugo' in summary_df.columns:
            summary_df = summary_df.drop(columns=['media_percentual_refugo'])
        return summary_df.merge(refugo, on=group_col, how='left')
    
    if not df_sos_analysis.empty:
        # Calcula colunas auxiliares e agregações para as tabelas
        df_sos_analysis['peso_boas'] = df_sos_analysis['quantidade'] * (df_sos_analysis['milheiro'] / 1000)
        
        # Análise por SOS - usa df_sos_analysis (com filtro de Data SOS)
        df_sos_only = df_sos_analysis[df_sos_analysis['sos'].isin(MAQUINAS_SOS)]
        machine_summary = df_sos_only.groupby('sos').agg(
            media_sacos_p_min=('velocidade_un_min', 'mean'),
            contagem_servico=('id', 'count'),
            soma_quant=('quantidade', 'sum'),
            media_tempo_acerto=('tempo_acerto_s', 'mean')
        ).reset_index()
        machine_summary = merge_refugo_consolidado(machine_summary, df_sos_only, 'sos', calc_media_refugo_sos_consolidada)
        
        media_percentual_refugo_total = calc_media_refugo_sos_consolidada(df_sos_only)
        
        refugo_total = df_sos_only['refugo_producao_total'].sum() if not df_sos_only.empty else 0
        peso_boas_total = df_sos_only['peso_boas'].sum() if not df_sos_only.empty else 0
        media_por_maquina = df_sos_only.groupby("sos")["refugo_pct"].mean().reset_index() if not df_sos_only.empty else pd.DataFrame()
        
        # Calcula média de sacos p/ min apenas para máquinas SOS
        media_sacos_p_min_total = df_sos_only['velocidade_un_min'].mean() if 'velocidade_un_min' in df_sos_only.columns and not df_sos_only.empty else 0
        
        machine_total = {
            'sos': 'Total Geral',
            'media_sacos_p_min': media_sacos_p_min_total,
            'contagem_servico': df_sos_only['id'].count() if not df_sos_only.empty else 0,
            'media_percentual_refugo': media_percentual_refugo_total,
            'soma_quant': df_sos_only['quantidade'].sum() if not df_sos_only.empty else 0,
            'media_tempo_acerto': None,
        }
        # Análise por Operador SOS - usa df_operator_analysis se houver filtros específicos, senão usa df_base (exclui ILSON)
        # Verifica se há filtros específicos de operador
        has_operator_filters = any([
            request.args.get('operator_servico'),
            request.args.get('operator_num_of'),
            request.args.get('operator_start_date'),
            request.args.get('operator_end_date'),
            request.args.getlist('operator_operadores'),
            request.args.getlist('operator_maquinas')
        ])
        
        df_operator_final = df_operator_analysis if has_operator_filters else df_sos_analysis.copy()
        
        if not df_operator_final.empty:
            # Filtra apenas operadores SOS (remove ILSON, VALDO e outros que não são SOS)
            df_operator_final = df_operator_final[df_operator_final['operador'].isin(OPERADORES_SOS)]
            df_operator_final['peso_boas'] = df_operator_final['quantidade'] * (df_operator_final['milheiro'] / 1000)
            operator_summary = df_operator_final.groupby('operador').agg(
            media_sacos_p_min=('velocidade_un_min', 'mean'),
            contagem_servico=('id', 'count'),
            media_total_acerto=('tempo_acerto_s', 'mean')
        ).reset_index()
            operator_summary = merge_refugo_consolidado(operator_summary, df_operator_final, 'operador', calc_media_refugo_sos_consolidada)
            # Garante que apenas operadores SOS apareçam nos resultados
            operator_summary = operator_summary[operator_summary['operador'].isin(OPERADORES_SOS)]
            operator_summary['media_total_acerto'] = operator_summary['media_total_acerto'].apply(format_seconds)
        operator_total = {
            'operador': 'Total Geral',
                'media_sacos_p_min': df_operator_final['velocidade_un_min'].mean() if 'velocidade_un_min' in df_operator_final.columns and not df_operator_final.empty else 0,
                'contagem_servico': df_operator_final['id'].count() if not df_operator_final.empty else 0,
                'media_percentual_refugo': calc_media_refugo_sos_consolidada(df_operator_final),
                'media_total_acerto': format_seconds(df_operator_final['tempo_acerto_s'].mean()) if not df_operator_final.empty else "00:00:00"
            }
        machine_summary['media_tempo_acerto'] = machine_summary['media_tempo_acerto'].apply(format_seconds)
        machine_total['media_tempo_acerto'] = format_seconds(df_sos_only['tempo_acerto_s'].mean()) if not df_sos_only.empty else "00:00:00"
        # Análise Impressora - usa df_impressora_analysis (com filtros específicos)
        df_impressora = df_impressora_analysis[df_impressora_analysis['impressora'] == 'IMPRESSORA'] if not df_impressora_analysis.empty else pd.DataFrame()
        impressora_summary = None
        impressora_total = None
        if not df_impressora.empty:
            impressora_summary = df_impressora.groupby('impressora').agg(
                media_sacos_p_min=('velocidade_un_min_flexo', 'mean'),
                contagem_servico=('id', 'count'),
                soma_quant=('quantidade_impressora', 'sum'),
                media_tempo_acerto=('tempo_acerto_impressora', 'mean')
            ).reset_index()
            impressora_summary = merge_refugo_consolidado(impressora_summary, df_impressora, 'impressora', calc_media_refugo_flexo_consolidada)
            impressora_summary['media_tempo_acerto'] = impressora_summary['media_tempo_acerto'].apply(format_seconds)
            
            impressora_total = {
                'impressora': 'Total Geral',
                'media_sacos_p_min': df_impressora['velocidade_un_min_flexo'].mean() if 'velocidade_un_min_flexo' in df_impressora.columns and not df_impressora.empty else 0,
                'contagem_servico': df_impressora['id'].count() if not df_impressora.empty else 0,
                'media_percentual_refugo': calc_media_refugo_flexo_consolidada(df_impressora),
                'soma_quant': df_impressora['quantidade_impressora'].sum() if not df_impressora.empty else 0,
                'media_tempo_acerto': format_seconds(df_impressora['tempo_acerto_impressora'].mean()) if not df_impressora.empty else "00:00:00",
            }
            impressora_summary = impressora_summary.to_dict('records')
        
        # Análise Robô - usa df_robo_analysis (com filtros: Serviço, Nº OF, Data Robô, Operador)
        df_robo = df_robo_analysis[(df_robo_analysis['robo_alca'].notna()) & (df_robo_analysis['robo_alca'].astype(str).str.strip() != '')] if not df_robo_analysis.empty else pd.DataFrame()
        if not df_robo.empty:
            robo_summary = df_robo.groupby('robo_alca').agg(
                contagem_servico=('id', 'count'),
                refugo_pecas=('refugo_robo', 'sum'),
                soma_quantidade_robo=('quantidade_robo', 'sum')
            ).reset_index()
            robo_summary = robo_summary.rename(columns={'robo_alca': 'robo'})
            robo_total = {
                'robo': 'Total Geral',
                'contagem_servico': int(df_robo['id'].count()),
                'refugo_pecas': float(df_robo['refugo_robo'].sum()) if 'refugo_robo' in df_robo.columns else 0,
                'soma_quantidade_robo': float(df_robo['quantidade_robo'].sum()) if 'quantidade_robo' in df_robo.columns else 0,
            }
            robo_summary = robo_summary.to_dict('records')
        else:
            robo_summary = []
            robo_total = None
        
        machine_summary = machine_summary.to_dict('records') if machine_summary is not None else []
        operator_summary = operator_summary.to_dict('records') if operator_summary is not None else []
    
    # Garantir robo_summary/robo_total quando df_sos_analysis está vazio (ex.: só filtros Robô)
    if robo_summary is None and not df_robo_analysis.empty:
        df_robo = df_robo_analysis[(df_robo_analysis['robo_alca'].notna()) & (df_robo_analysis['robo_alca'].astype(str).str.strip() != '')] if not df_robo_analysis.empty else pd.DataFrame()
        if not df_robo.empty:
            robo_summary = df_robo.groupby('robo_alca').agg(
                contagem_servico=('id', 'count'),
                refugo_pecas=('refugo_robo', 'sum'),
                soma_quantidade_robo=('quantidade_robo', 'sum')
            ).reset_index()
            robo_summary = robo_summary.rename(columns={'robo_alca': 'robo'})
            robo_total = {
                'robo': 'Total Geral',
                'contagem_servico': int(df_robo['id'].count()),
                'refugo_pecas': float(df_robo['refugo_robo'].sum()) if 'refugo_robo' in df_robo.columns else 0,
                'soma_quantidade_robo': float(df_robo['quantidade_robo'].sum()) if 'quantidade_robo' in df_robo.columns else 0,
            }
            robo_summary = robo_summary.to_dict('records')
        else:
            robo_summary = []
            robo_total = None
    if robo_summary is None:
        robo_summary = []
    
    # Função auxiliar para formatar segundos (definida aqui para uso em todas as análises)
    def format_seconds(seconds):
        if pd.isna(seconds) or seconds == 0: return "00:00:00"
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02}:{minutes:02}:{secs:02}"
    
    # Análise por Operador Impressora - usa df_operator_impressora_analysis se houver filtros específicos
    # Verifica se há filtros específicos de operador impressora
    has_operator_impressora_filters = any([
        request.args.get('operator_impressora_servico'),
        request.args.get('operator_impressora_num_of'),
        request.args.get('operator_impressora_start_date_impressora'),
        request.args.get('operator_impressora_end_date_impressora'),
        request.args.getlist('operator_impressora_operadores')
    ])
    
    # Se não houver filtros específicos, usa df_impressora_analysis como base (já filtrado pelos filtros gerais)
    if has_operator_impressora_filters:
        df_operator_impressora_final = df_operator_impressora_analysis.copy()
    else:
        # Usa df_impressora_analysis se disponível, senão DataFrame vazio
        df_operator_impressora_final = df_impressora_analysis.copy() if not df_impressora_analysis.empty else pd.DataFrame()
    
    if not df_operator_impressora_final.empty:
        # Filtra apenas operadores Impressora e apenas registros com impressora preenchida
        df_operator_impressora_final = df_operator_impressora_final[
            (df_operator_impressora_final['operador_impressora'].isin(OPERADORES_IMPRESSORA)) &
            (df_operator_impressora_final['impressora'] == 'IMPRESSORA')
        ]
        
        if not df_operator_impressora_final.empty:
            operator_impressora_summary = df_operator_impressora_final.groupby('operador_impressora').agg(
                media_sacos_p_min=('velocidade_un_min_flexo', 'mean'),
            contagem_servico=('id', 'count'),
                media_total_acerto=('tempo_acerto_impressora', 'mean')
        ).reset_index()
            operator_impressora_summary = merge_refugo_consolidado(
                operator_impressora_summary, df_operator_impressora_final, 'operador_impressora', calc_media_refugo_flexo_consolidada
            )
            operator_impressora_summary.rename(columns={'operador_impressora': 'operador'}, inplace=True)
            operator_impressora_summary['media_total_acerto'] = operator_impressora_summary['media_total_acerto'].apply(format_seconds)
            operator_impressora_total = {
                'operador': 'Total Geral',
                'media_sacos_p_min': df_operator_impressora_final['velocidade_un_min_flexo'].mean() if 'velocidade_un_min_flexo' in df_operator_impressora_final.columns and not df_operator_impressora_final.empty else 0,
                'contagem_servico': df_operator_impressora_final['id'].count() if not df_operator_impressora_final.empty else 0,
                'media_percentual_refugo': calc_media_refugo_flexo_consolidada(df_operator_impressora_final),
                'media_total_acerto': format_seconds(df_operator_impressora_final['tempo_acerto_impressora'].mean()) if not df_operator_impressora_final.empty else "00:00:00"
            }
            operator_impressora_summary = operator_impressora_summary.to_dict('records') if operator_impressora_summary is not None else []
        else:
            operator_impressora_summary = []
            operator_impressora_total = None
    else:
        operator_impressora_summary = []
        operator_impressora_total = None

    preserved_args = request.args.copy()
    preserved_args.pop('export', None)
    preserved_args.pop('section', None)

    export_section = request.args.get('section', '').strip()
    if request.args.get('export') == 'excel' and export_section:
        export_map = {
            'sos': (machine_summary, machine_total),
            'impressora': (impressora_summary, impressora_total),
            'robo': (robo_summary, robo_total),
            'operator_sos': (operator_summary, operator_total),
            'operator_impressora': (operator_impressora_summary, operator_impressora_total),
        }
        if export_section not in export_map:
            flash(f'Seção de exportação inválida: {export_section}', 'danger')
            return redirect(url_for('main.analise', **preserved_args))
        try:
            summary_data, total_data = export_map[export_section]
            output, filename = _exportar_analise_excel(export_section, summary_data, total_data)
            return send_file(output, download_name=filename, as_attachment=True)
        except Exception as e:
            flash(f'Erro ao exportar: {e}', 'danger')
            return redirect(url_for('main.analise', **preserved_args))
    
    return render_template('analise.html', machine_summary=machine_summary, operator_summary=operator_summary, machine_total=machine_total, operator_total=operator_total, impressora_summary=impressora_summary, impressora_total=impressora_total, robo_summary=robo_summary, robo_total=robo_total, operator_impressora_summary=operator_impressora_summary, operator_impressora_total=operator_impressora_total, all_operadores=ALL_OPERADORES, all_operadores_sos=OPERADORES_SOS, operadores_impressora=OPERADORES_IMPRESSORA, operadores_robo=OPERADORES_ROBO, operadores_sos=OPERADORES_SOS, preserved_args=preserved_args, action_url=url_for('main.analise')) 