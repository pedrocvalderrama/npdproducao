import re

from .config import IDEAL_SETUP_TIMES_MIN, IDEAL_SCRAP_RATES_SOS_PCT
from .services.formato_service import obter_ideal_speed_rates

OBSERVACOES_SEP = '   |   '
_OBS_LABEL_TO_KEY = {'Impressora': 'impressora', 'SOS': 'sos', 'Robô': 'robo', 'Robo': 'robo'}
_OBS_KEY_TO_LABEL = {'impressora': 'Impressora', 'sos': 'SOS', 'robo': 'Robô'}

# Função auxiliar para converter valores do formulário para float, tratando strings vazias
def safe_float(value, default=0.0):
    """Converte um valor para float, tratando strings vazias e None."""
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

# Função auxiliar para converter valores do formulário para int, tratando strings vazias
def safe_int(value, default=0):
    """Converte um valor para int, tratando strings vazias e None."""
    if value is None or value == '':
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

# Converte uma string de tempo (HH:MM) para segundos.
def get_seconds_from_time(time_str):
    """Converte uma string de tempo (HH:MM) para segundos."""
    if not time_str:
        return 0
    h, m = map(int, time_str.split(':'))
    return h * 3600 + m * 60

PROD_DIA_KEYS = [
    ('inicio_prod', 'fim_prod'),
    ('inicio_prod_2', 'fim_prod_2'),
    ('inicio_prod_3', 'fim_prod_3'),
    ('inicio_prod_4', 'fim_prod_4'),
]

PROD_IMPRESSORA_DIA_KEYS = [
    ('inicio_prod_impressora', 'fim_prod_impressora'),
    ('inicio_prod_impressora_2', 'fim_prod_impressora_2'),
    ('inicio_prod_impressora_3', 'fim_prod_impressora_3'),
    ('inicio_prod_impressora_4', 'fim_prod_impressora_4'),
]

def parse_observacoes(text):
    """Separa observações unificadas nos campos Impressora, SOS e Robô."""
    result = {'impressora': '', 'sos': '', 'robo': ''}
    text = (text or '').strip()
    if not text:
        return result
    matched = False
    for part in re.split(r'\s+\|\s+', text):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(Impressora|SOS|Robô|Robo):\s*'(.*)'\s*$", part, re.DOTALL)
        if m:
            matched = True
            key = _OBS_LABEL_TO_KEY.get(m.group(1))
            if key:
                result[key] = m.group(2).replace("''", "'")
    if not matched:
        result['robo'] = text
    return result

def build_observacoes(impressora='', sos='', robo=''):
    """Monta o texto único de observações para gravação no banco."""
    parts = []
    for key in ('impressora', 'sos', 'robo'):
        text = {'impressora': impressora, 'sos': sos, 'robo': robo}[key]
        text = (text or '').strip()
        if text:
            escaped = text.replace("'", "''")
            parts.append(f"{_OBS_KEY_TO_LABEL[key]}: '{escaped}'")
    return OBSERVACOES_SEP.join(parts)

def observacoes_from_form(form_data):
    """Lê os três campos do formulário e retorna observações unificadas."""
    return build_observacoes(
        form_data.get('observacoes_impressora', ''),
        form_data.get('observacoes_sos', ''),
        form_data.get('observacoes_robo', ''),
    )

def enrich_lancamento_observacoes(lancamento):
    """Adiciona observacoes_impressora/sos/robo ao lançamento para o formulário."""
    if lancamento is None:
        return None
    data = dict(lancamento)
    parsed = parse_observacoes(data.get('observacoes', ''))
    data['observacoes_impressora'] = parsed['impressora']
    data['observacoes_sos'] = parsed['sos']
    data['observacoes_robo'] = parsed['robo']
    return data

def calc_tempo_producao_impressora(form_data):
    """Calcula tempo total de produção Impressora (soma dos dias 1 a 4)."""
    return sum(
        calc_tempo_producao_segmento(form_data.get(k1), form_data.get(k2))
        for k1, k2 in PROD_IMPRESSORA_DIA_KEYS
    )

def calc_tempo_producao_segmento(inicio, fim):
    """Calcula duração em segundos entre início e fim de produção (suporta virada de dia)."""
    inicio = (inicio or '').strip()
    fim = (fim or '').strip()
    if not inicio or not fim:
        return 0
    inicio_s = get_seconds_from_time(inicio)
    fim_s = get_seconds_from_time(fim)
    return fim_s - inicio_s if fim_s >= inicio_s else (fim_s - inicio_s) + 24 * 3600

# Calcula as métricas de produção a partir dos dados do formulário
def calcular_metricas_producao(form_data):
    try:
        # Extrai e converte os dados do formulário
        m = safe_float(form_data.get('milheiro', 0))
        # Calcula o refugo total como soma das 5 colunas de refugo
        rf = safe_float(form_data.get('refugo_flexo', 0))
        rpi = safe_float(form_data.get('refugo_pre_impresso', 0))
        rs = safe_float(form_data.get('refugo_sos', 0))
        raf = safe_float(form_data.get('refugo_acerto_flexo', 0))
        ras = safe_float(form_data.get('refugo_acerto_sos', 0))
        peso_unidade = m / 1000 if m > 0 else 0
        refugo_robo = safe_float(form_data.get('refugo_robo', 0))
        refugo_inspecao_final = safe_float(form_data.get('refugo_inspecao_final', 0))
        rsos = rs + ras  # Refugo SOS (soma dos 3 tipos referentes a SOS)
        rflexo = rf + raf + rpi  # Refugo Flexo (soma dos 2 tipos referentes a Flexo)
        r = rf + rpi + rs + raf + ras  # Refugo total (soma em kg dos refugos da produção SOS e Flexo)
        
        qsos = safe_int(form_data.get('quantidade', 0))  # Quantidade SOS
        qflexo = safe_int(form_data.get('quantidade_impressora', 0))  # Quantidade Impressora
        sos = form_data.get('sos', '') or ''
        formato = form_data.get('formato', '') or ''
        papel = form_data.get('papel', '') or ''
        qtd_cliches = safe_int(form_data.get('qtd_cliches', 0))

        # Calcula tempo de produção SOS (soma dos dias 1 a 4)
        actual_prod_time_sos = sum(
            calc_tempo_producao_segmento(form_data.get(k1), form_data.get(k2))
            for k1, k2 in PROD_DIA_KEYS
        )

        # Calcula tempo de produção Impressora (soma dos dias 1 a 4)
        actual_prod_time_impressora = calc_tempo_producao_impressora(form_data)

        # Calcula tempo de acerto
        actual_setup_time_s = 0
        inicio_acerto = (form_data.get('inicio_acerto') or '').strip()
        fim_acerto = (form_data.get('fim_acerto') or '').strip()
        if inicio_acerto and fim_acerto:
            inicio_s = get_seconds_from_time(inicio_acerto)
            fim_s = get_seconds_from_time(fim_acerto)
            actual_setup_time_s = fim_s - inicio_s if fim_s >= inicio_s else (fim_s - inicio_s) + 24 * 3600

        # Calcula perdas, velocidade, peso e refugo
        perdas_un = ((rsos + rflexo) * 1000) / m if m > 0 else 0
        perdas_total_kg = (peso_unidade * (refugo_robo + refugo_inspecao_final)) + r
        refugo_robo_kg = refugo_robo * peso_unidade
        refugo_inspecao_final_kg = refugo_inspecao_final * peso_unidade
        actual_speed_un_min_sos = (qsos / (actual_prod_time_sos / 60)) if actual_prod_time_sos > 0 else 0
        actual_speed_un_min_flexo = (qflexo / (actual_prod_time_impressora / 60)) if actual_prod_time_impressora > 0 else 0
        kg_por_unidade = m / 1000 if m > 0 else 0
        peso_boas_sos = qsos * kg_por_unidade
        peso_boas_flexo = qflexo * kg_por_unidade
        actual_scrap_pct = (rsos / (peso_boas_sos + rsos)) * 100 if peso_boas_sos > 0 else 0
        actual_scrap_pct_flexo = (rflexo / (peso_boas_flexo + rflexo)) * 100 if peso_boas_flexo > 0 else 0

        # Define velocidade ideal conforme formato (SOS sempre usa formato)
        ideal_speed_un_h = obter_ideal_speed_rates().get(formato, 0)
        ideal_speed_un_min = ideal_speed_un_h / 60
        speed_performance = (actual_speed_un_min_sos / ideal_speed_un_min) if actual_speed_un_min_sos > 0 and ideal_speed_un_min > 0 else 0

        # Calcula tempo de acerto ideal e performance
        ideal_setup_time_s = IDEAL_SETUP_TIMES_MIN.get(qtd_cliches, 0) * 60
        setup_performance = (ideal_setup_time_s / actual_setup_time_s) if actual_setup_time_s > 0 else 1

        # Define refugo ideal conforme papel (SOS sempre usa papel)
        ideal_scrap_pct = IDEAL_SCRAP_RATES_SOS_PCT.get(papel, 100.0)
        actual_yield = 100.0 - actual_scrap_pct
        ideal_yield = 100.0 - ideal_scrap_pct
        scrap_performance = (actual_yield / ideal_yield) if ideal_yield > 0 else 0
        # Calcula eficiência total
        total_efficiency = (speed_performance * setup_performance * scrap_performance) * 100
        return {
            "refugo_pct": actual_scrap_pct, "refugo_pct_flexo": actual_scrap_pct_flexo, "eficiencia_pct": total_efficiency,
            "velocidade_un_min": actual_speed_un_min_sos, "velocidade_un_min_flexo": actual_speed_un_min_flexo, "perdas_un": perdas_un,
            "perdas_total_kg": perdas_total_kg, "refugo_robo_kg": refugo_robo_kg, "refugo_inspecao_final_kg": refugo_inspecao_final_kg,
            "tempo_prod_s": actual_prod_time_sos, "tempo_acerto_s": actual_setup_time_s
        }
    except Exception as e:
        # Log do erro para debug (pode ser removido em produção)
        import traceback
        print(f"Erro ao calcular métricas: {e}")
        print(traceback.format_exc())
        # Retorna valores padrão em caso de erro
        return {"refugo_pct": 0, "refugo_pct_flexo": 0, "eficiencia_pct": 0, "velocidade_un_min": 0, "velocidade_un_min_flexo": 0, "perdas_un": 0, "perdas_total_kg": 0, "refugo_robo_kg": 0, "refugo_inspecao_final_kg": 0, "tempo_prod_s": 0, "tempo_acerto_s": 0} 