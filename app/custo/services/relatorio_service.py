"""
Serviços relacionados a relatórios de produção e custos
"""
import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from database.connection import get_db
from app.custo.services.custo_service import (
    obter_custos_papeis,
    obter_custo_operacional_atual,
    obter_custo_operacional_por_despesa,
    obter_custo_alca_natural,
    obter_custo_alca_branca,
    is_papel_branco,
    renomear_despesa_operacional,
)
from app.custo.utils.formatters import formatar_data_br


def obter_dados_relatorio(data_inicio=None, data_fim=None, servico=None, num_of=None, start_date=None, end_date=None):
    """
    Obtém os dados completos do relatório de custos com cálculos.
    Inclui lógica condicional baseada no tipo:
    - SACOLA: usa todas as despesas operacionais (incluindo alça)
      - papel branco (BRANCO 110G / 110GRS / 90GRS / 80GRS): ALÇA BRANCA
      - demais papéis: ALÇA NATURAL
    - CARTUCHO: usa apenas a despesa TINTA
    - SEDA: despesas operacionais sem alça
    """
    renomear_despesa_operacional("ALÇA", "ALÇA NATURAL")
    custo_op_unitario_total = obter_custo_operacional_atual()
    custo_op_alca_natural = obter_custo_alca_natural()
    custo_op_alca_branca = obter_custo_alca_branca()
    # Base sem as variantes de alça (apenas uma delas entra por pedido)
    custo_op_unitario_base = (
        custo_op_unitario_total - custo_op_alca_natural - custo_op_alca_branca
    )
    if custo_op_unitario_base < 0:
        custo_op_unitario_base = 0.0

    custo_op_tinta_unitario = obter_custo_operacional_por_despesa("TINTA")
    custos_papel = obter_custos_papeis()

    conn = get_db()
    dados = []
    try:
        clauses = []
        params = []
        # Filtros de data: priorizar data_inicio/data_fim se existirem, senão usar start_date/end_date
        if data_inicio or data_fim:
            if data_inicio:
                clauses.append("data >= ?")
                params.append(data_inicio)
            if data_fim:
                clauses.append("data <= ?")
                params.append(data_fim)
        elif start_date or end_date:
            if start_date and end_date:
                clauses.append("data BETWEEN ? AND ?")
                params.extend([start_date, end_date])
            elif start_date:
                clauses.append("data >= ?")
                params.append(start_date)
            elif end_date:
                clauses.append("data <= ?")
                params.append(end_date)
        # Filtro por Serviço (busca parcial)
        if servico and servico.strip():
            clauses.append("servico LIKE ?")
            params.append(f"%{servico.strip()}%")
        # Filtro por Nº de OF
        if num_of and num_of.strip():
            clauses.append("num_of LIKE ?")
            params.append(f"%{num_of.strip()}%")

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        query = f"""
            SELECT num_of, data, servico, operador, numero_pedido, papel, formato, tipo,
                   milheiro, quantidade,
                   COALESCE(refugo_acerto_sos, 0) as refugo_acerto_sos,
                   COALESCE(refugo_sos, 0) as refugo_sos,
                   COALESCE(refugo_pre_impresso, 0) as refugo_pre_impresso,
                   COALESCE(refugo_acerto_flexo, 0) as refugo_acerto_flexo,
                   COALESCE(refugo_flexo, 0) as refugo_flexo,
                   COALESCE(refugo_producao_total, 0) as refugo_producao_total,
                   COALESCE(consumo_util, 0) as consumo_util,
                   COALESCE(consumo_total, 0) as consumo_total
            FROM producao {where_clause}
            ORDER BY (numero_pedido IS NULL), numero_pedido DESC, num_of DESC
        """

        rows = conn.execute(query, tuple(params)).fetchall()

        for r in rows:
            d = dict(r)
            of = d.get('num_of')

            milheiro = float(d.get('milheiro') or 0)
            qtd = int(d.get('quantidade') or 0)

            ref_sos = float(d.get('refugo_acerto_sos') or 0) + \
                     float(d.get('refugo_sos') or 0) + \
                     float(d.get('refugo_pre_impresso') or 0)

            ref_imp = float(d.get('refugo_acerto_flexo') or 0) + \
                     float(d.get('refugo_flexo') or 0)

            ref_total = float(d.get('refugo_producao_total') or 0)
            cons_util = float(d.get('consumo_util') or 0)
            cons_total_kg = float(d.get('consumo_total') or 0)
            tipo = d.get('tipo', '').upper()

            c_papel_kg = custos_papel.get(d.get('papel'), 0.0)
            custo_mat_total = cons_total_kg * c_papel_kg

            if tipo == 'CARTUCHO':
                custo_op_unitario_final = custo_op_tinta_unitario
            elif tipo == 'SACOLA':
                custo_alca = (
                    custo_op_alca_branca
                    if is_papel_branco(d.get('papel'))
                    else custo_op_alca_natural
                )
                custo_op_unitario_final = custo_op_unitario_base + custo_alca
            elif tipo == 'SEDA':
                custo_op_unitario_final = custo_op_unitario_base
            else:
                custo_op_unitario_final = custo_op_unitario_base

            custo_op_total_pedido = qtd * custo_op_unitario_final
            custo_final = custo_mat_total + custo_op_total_pedido

            dados.append({
                "num_of": of,
                "data": formatar_data_br(d.get('data')),
                "servico": d.get('servico'),
                "operador": d.get('operador'),
                "numero_pedido": d.get('numero_pedido'),
                "papel": d.get('papel'),
                "formato": d.get('formato'),
                "tipo": d.get('tipo'),
                "milheiro": milheiro,
                "quantidade": qtd,
                "ref_sos": ref_sos,
                "ref_imp": ref_imp,
                "ref_total": ref_total,
                "cons_util": cons_util,
                "cons_total": cons_total_kg,
                "custo_kg_papel": c_papel_kg,
                "custo_mat_total": custo_mat_total,
                "custo_op_total": custo_op_total_pedido,
                "custo_final": custo_final
            })
    except Exception as e:
        print(f"Erro obtendo dados: {e}")
    finally:
        conn.close()

    return dados, custo_op_unitario_total


def exportar_custo_csv(data_inicio=None, data_fim=None, servico=None, num_of=None, start_date=None, end_date=None):
    """Exporta dados do relatório de custos para CSV com formato PT-BR (vírgula como separador decimal)."""
    import csv
    import io

    dados, _ = obter_dados_relatorio(data_inicio, data_fim, servico, num_of, start_date, end_date)

    def formatar_numero_pt_br(valor, decimais=2):
        """Converte número para formato PT-BR (vírgula como separador decimal)."""
        if valor is None:
            return ''
        try:
            return f"{float(valor):.{decimais}f}".replace('.', ',')
        except (ValueError, TypeError):
            return str(valor) if valor else ''

    out = io.StringIO()
    w = csv.writer(out, delimiter=';')
    w.writerow([
        'OF', 'Data', 'Servico', 'Nº do Pedido', 'Papel', 'Formato', 'Qtd', 'Milheiro',
        'Refugo SOS', 'Refugo Imp', 'Refugo Total', 'Consumo Util', 'Consumo Total',
        'Custo Papel', 'Custos Adicionais', 'Custo Final'
    ])

    for d in dados:
        w.writerow([
            d['num_of'], d['data'], d['servico'], d.get('numero_pedido', '') or '', d['papel'], d['formato'],
            d['quantidade'], formatar_numero_pt_br(d['milheiro'], 2), formatar_numero_pt_br(d['ref_sos'], 2), 
            formatar_numero_pt_br(d['ref_imp'], 2), formatar_numero_pt_br(d['ref_total'], 2), 
            formatar_numero_pt_br(d['cons_util'], 3), formatar_numero_pt_br(d['cons_total'], 3),
            formatar_numero_pt_br(d['custo_mat_total'], 2), formatar_numero_pt_br(d['custo_op_total'], 2), 
            formatar_numero_pt_br(d['custo_final'], 2)
        ])

    return out.getvalue()
