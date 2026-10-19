"""
Service de persistência de lançamentos de produção.

Centraliza o cálculo dos campos derivados (refugo total, consumo, tempos,
etc.) e a montagem do INSERT/UPDATE em `producao`. Antes, esse cálculo e a
query de ~60 colunas apareciam duplicados nas rotas /lancar e /editar; agora
ambas chamam as mesmas funções aqui, então uma correção de regra de negócio
só precisa ser feita em um lugar.
"""
from ..business import (
    calc_tempo_producao_impressora,
    calcular_metricas_producao,
    get_seconds_from_time,
    observacoes_from_form,
)
from ..utils import safe_get_float, safe_get_int, safe_get_str


def validar_form_producao(form):
    """Retorna mensagem de erro se o formulário for inválido, senão None."""
    quantidade_robo = safe_get_int(form, "quantidade_robo", 0)
    robo_alca = safe_get_str(form, "robo_alca")
    if quantidade_robo > 0 and not robo_alca:
        return (
            "Se a Quantidade Robô for maior que zero, é obrigatório selecionar o Robô Alça."
        )
    return None


def _calcular_tempo_acerto_impressora(form):
    inicio = form.get('inicio_acerto_impressora')
    fim = form.get('fim_acerto_impressora')
    if not inicio or not fim:
        return 0
    inicio_s = get_seconds_from_time(inicio)
    fim_s = get_seconds_from_time(fim)
    return fim_s - inicio_s if fim_s >= inicio_s else (fim_s - inicio_s) + 24 * 3600


def montar_campos_producao(form):
    """
    A partir do form de lançamento/edição, calcula os campos derivados e
    devolve um dict {coluna: valor} pronto para INSERT/UPDATE em `producao`
    (mesmos cálculos e mesma semântica que existiam em /lancar e /editar).
    """
    metricas = calcular_metricas_producao(form)

    refugo_flexo = safe_get_float(form, "refugo_flexo", 0.0)
    refugo_pre_impresso = safe_get_float(form, "refugo_pre_impresso", 0.0)
    refugo_sos = safe_get_float(form, "refugo_sos", 0.0)
    refugo_acerto_flexo = safe_get_float(form, "refugo_acerto_flexo", 0.0)
    refugo_acerto_sos = safe_get_float(form, "refugo_acerto_sos", 0.0)
    refugo_total = refugo_flexo + refugo_pre_impresso + refugo_sos + refugo_acerto_flexo + refugo_acerto_sos

    quantidade = safe_get_float(form, "quantidade", 0.0)
    milheiro = safe_get_float(form, "milheiro", 0.0)
    # Mesma lógica do lançamento de custo: (Quantidade SOS / 1000) × milheiro
    consumo_util = (quantidade / 1000.0) * milheiro

    perdas_geral_kg = metricas["perdas_total_kg"]
    consumo_total = consumo_util + perdas_geral_kg

    refugo_robo = safe_get_float(form, "refugo_robo", 0.0)
    refugo_inspecao_final = safe_get_float(form, "refugo_inspecao_final", 0.0)
    perdas_geral = metricas["perdas_un"] + refugo_robo + refugo_inspecao_final

    tempo_acerto_impressora = _calcular_tempo_acerto_impressora(form)
    tempo_prod_impressora = calc_tempo_producao_impressora(form)
    numero_pedido = safe_get_int(form, "numero_pedido", None)

    return {
        "num_of": safe_get_str(form, "num_of"),
        "data": safe_get_str(form, "data"),
        "data_impressora": safe_get_str(form, "data_impressora"),
        "data_inspecao": safe_get_str(form, "data_inspecao"),
        "data_robo": safe_get_str(form, "data_robo"),
        "operador": safe_get_str(form, "operador"),
        "operador_impressora": safe_get_str(form, "operador_impressora"),
        "operador_robo": safe_get_str(form, "operador_robo"),
        "impressora": safe_get_str(form, "impressora"),
        "sos": safe_get_str(form, "sos"),
        "robo_alca": safe_get_str(form, "robo_alca"),
        "qtd_cliches": safe_get_int(form, "qtd_cliches", 1),
        "tipo": safe_get_str(form, "tipo"),
        "formato": safe_get_str(form, "formato"),
        "papel": safe_get_str(form, "papel"),
        "servico": safe_get_str(form, "servico"),
        "milheiro": milheiro,
        "tipo_impressao": safe_get_str(form, "tipo_impressao", ""),
        "refugo_flexo": refugo_flexo,
        "refugo_pre_impresso": refugo_pre_impresso,
        "refugo_sos": refugo_sos,
        "refugo_robo": refugo_robo,
        "refugo_inspecao_final": refugo_inspecao_final,
        "refugo_robo_kg": metricas["refugo_robo_kg"],
        "refugo_inspecao_final_kg": metricas["refugo_inspecao_final_kg"],
        "refugo_acerto_flexo": refugo_acerto_flexo,
        "refugo_acerto_sos": refugo_acerto_sos,
        "refugo_producao_total": refugo_total,
        "consumo_util": consumo_util,
        "consumo_total": consumo_total,
        "quantidade_comanda": safe_get_int(form, "quantidade_comanda", 0),
        "quantidade": quantidade,
        "quantidade_impressora": safe_get_int(form, "quantidade_impressora", 0),
        "quantidade_inspecao_geral": safe_get_int(form, "quantidade_inspecao_geral", 0),
        "quantidade_robo": safe_get_int(form, "quantidade_robo", 0),
        "inicio_prod": safe_get_str(form, "inicio_prod"),
        "fim_prod": safe_get_str(form, "fim_prod"),
        "inicio_prod_2": safe_get_str(form, "inicio_prod_2"),
        "fim_prod_2": safe_get_str(form, "fim_prod_2"),
        "inicio_prod_3": safe_get_str(form, "inicio_prod_3"),
        "fim_prod_3": safe_get_str(form, "fim_prod_3"),
        "inicio_prod_4": safe_get_str(form, "inicio_prod_4"),
        "fim_prod_4": safe_get_str(form, "fim_prod_4"),
        "inicio_prod_impressora": safe_get_str(form, "inicio_prod_impressora"),
        "fim_prod_impressora": safe_get_str(form, "fim_prod_impressora"),
        "inicio_prod_impressora_2": safe_get_str(form, "inicio_prod_impressora_2"),
        "fim_prod_impressora_2": safe_get_str(form, "fim_prod_impressora_2"),
        "inicio_prod_impressora_3": safe_get_str(form, "inicio_prod_impressora_3"),
        "fim_prod_impressora_3": safe_get_str(form, "fim_prod_impressora_3"),
        "inicio_prod_impressora_4": safe_get_str(form, "inicio_prod_impressora_4"),
        "fim_prod_impressora_4": safe_get_str(form, "fim_prod_impressora_4"),
        "inicio_acerto": safe_get_str(form, "inicio_acerto"),
        "fim_acerto": safe_get_str(form, "fim_acerto"),
        "inicio_acerto_impressora": safe_get_str(form, "inicio_acerto_impressora"),
        "fim_acerto_impressora": safe_get_str(form, "fim_acerto_impressora"),
        "observacoes": observacoes_from_form(form),
        "refugo_pct": metricas["refugo_pct"],
        "refugo_pct_flexo": metricas["refugo_pct_flexo"],
        "eficiencia_pct": metricas["eficiencia_pct"],
        "velocidade_un_min": metricas["velocidade_un_min"],
        "velocidade_un_min_flexo": metricas["velocidade_un_min_flexo"],
        "perdas_un": metricas["perdas_un"],
        "perdas_geral": perdas_geral,
        "perdas_geral_kg": perdas_geral_kg,
        "tempo_prod_s": metricas["tempo_prod_s"],
        "tempo_acerto_s": metricas["tempo_acerto_s"],
        "tempo_prod_impressora": tempo_prod_impressora,
        "tempo_acerto_impressora": tempo_acerto_impressora,
        "numero_pedido": numero_pedido,
    }


def inserir_producao(conn, campos):
    """Insere um novo registro em `producao` a partir do dict de campos."""
    colunas = list(campos.keys())
    placeholders = ", ".join(["?"] * len(colunas))
    sql = f"INSERT INTO producao ({', '.join(colunas)}) VALUES ({placeholders})"
    conn.execute(sql, tuple(campos.values()))


def atualizar_producao(conn, campos, registro_id):
    """Atualiza um registro existente em `producao` pelo id."""
    colunas = list(campos.keys())
    set_clause = ", ".join(f"{c}=?" for c in colunas)
    sql = f"UPDATE producao SET {set_clause} WHERE id = ?"
    conn.execute(sql, tuple(campos.values()) + (registro_id,))


def salvar_producao(conn, form):
    """
    Lógica usada pela rota /lancar: se já existir um registro com o mesmo
    num_of, atualiza; senão, insere um novo. Retorna True se foi UPDATE,
    False se foi INSERT (para a mensagem flash adequada).
    """
    campos = montar_campos_producao(form)
    existente = conn.execute(
        "SELECT id FROM producao WHERE num_of = ?", (campos["num_of"],)
    ).fetchone()
    if existente:
        atualizar_producao(conn, campos, existente["id"])
        return True
    inserir_producao(conn, campos)
    return False
