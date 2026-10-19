"""
Seed idempotente: copia formatos/tolerâncias legados (antes hardcoded) para o banco.

Não altera producao.formato — só preenche formatos_cadastro / formato_tolerancias
com as mesmas strings canônicas usadas nos lançamentos.
"""
import logging

from ..models import get_db_connection

logger = logging.getLogger(__name__)

# Snapshot dos dados que viviam em config.py + WEIGHT_TOLERANCES_DEFAULT
# (congelados aqui para a migração continuar após esvaziar o config).

_SEED_SPEED = {
    '10X19X05': 4100, '10X25X05': 4100, '12X25X07': 4100, '15X25X07': 4100,
    '18X30X10': 4100, '18X35X10': 4000, '20X30': 3600, '22X30X12': 4100,
    '22X40X12': 3900, '24X32X14,5': 3900, '24X35X14,5': 3800, '32X30X12': 4000,
    '32X39X12': 3600, '32X40X12': 3600, '35X45X14': 3200, '32X45X12': 3200,
    '32X30X16': 3300, '28X31X20': 3200, '28X32X17,5': 3300, '32X45X16': 3200,
    '25X30X9': 3900, '18X25X10': 4100, '25X25X9': 3700, '29X40X15': 3700,
    '25X40X14': 3900, '25X30X14': 4000, '27X32X17': 3300, '30X38': 3600,
    '31X34X12': 3900, '31X37X12': 3800, '40X45X14': 3000, '31X31X18': 3700,
    '31X31X16': 3700,
}

_SEED_LARGURA = {
    '10X19X05': 32, '10X25X05': 40, '12X25X07': 40, '15X25X07': 46,
    '18X25X10': 58, '18X30X10': 58, '18X35X10': 58,
    '20X30': 30, '22X30X12': 70, '22X40X12': 70, '25X30X9': 70, '25X25X9': 70,
    '24X32X14,5': 80, '24X35X14,5': 80, '25X30X14': 80, '25X40X14': 80,
    '27X32X17': 90, '28X32X17,5': 90, '29X40X15': 90, '30X38': 30,
    '31X34X12': 90, '31X37X12': 90, '32X30X12': 90, '32X39X12': 90,
    '32X40X12': 90, '32X45X12': 90,
    '31X31X18': 99, '28X31X20': 99, '32X30X16': 99, '32X45X16': 99, '35X45X14': 99,
    '40X45X14': 110,
    # Legado só em IDEAL_SPEED_RATES — mesma família de 31X31X18
    '31X31X16': 99,
}

_SEED_FORMATOS = [
    '10X19X05', '10X25X05', '12X25X07', '15X25X07', '18X25X10', '18X30X10', '18X35X10',
    '20X30', '22X30X12',
    '22X40X12', '24X32X14,5', '24X35X14,5', '25X25X9', '25X30X9', '25X30X14',
    '25X40X14', '27X32X17', '28X32X17,5', '29X40X15', '30X38', '31X31X18', '31X34X12',
    '31X37X12', '28X31X20', '32X30X12', '32X39X12', '32X40X12', '32X45X12',
    '32X45X16', '32X30X16', '35X45X14', '40X45X14',
    '31X31X16',
]

_SEED_TOLERANCIAS = {
    'BRANCO 110G': {
        '10X19X05': {'min': 7.00, 'max': 9.50}, '10X25X05': {'min': 9.21, 'max': 12.50},
        '12X25X07': {'min': 7, 'max': 9}, '15X25X07': {'min': 8, 'max': 10},
        '18X30X10': {'min': 25.52, 'max': 29.02}, '22X30X12': {'min': 30.80, 'max': 34.06},
        '22X40X12': {'min': 38.50, 'max': 41.50}, '32X30X12': {'min': 39.60, 'max': 45.60},
        '32X40X12': {'min': 49.50, 'max': 56.50}, '35X45X14': {'min': 59.90, 'max': 66.90},
        '32X45X12': {'min': 55.44, 'max': 61.74}, '32X30X16': {'min': 43.56, 'max': 47.56},
        '28X31X20': {'min': 49.01, 'max': 53.01}, '32X45X16': {'min': 59.90, 'max': 65.90},
        '25X30X9': {'min': 30.80, 'max': 34.30}, '18X25X10': {'min': 22.33, 'max': 26.63},
        '25X25X9': {'min': 26.95, 'max': 31.25}, '29X40X15': {'min': 49.50, 'max': 53.80},
        '25X40X14': {'min': 44.00, 'max': 48.30}, '25X30X14': {'min': 35.20, 'max': 39.50},
        '40X45X14': {'min': 66.55, 'max': 73.55}, '31X31X18': {'min': 49.01, 'max': 55.01},
        '18X35X10': {'min': 25, 'max': 29}, '24X32X14,5': {'min': 30, 'max': 36},
        '24X35X14,5': {'min': 35, 'max': 39}, '31X34X12': {'min': 37, 'max': 43},
        '31X37X12': {'min': 40, 'max': 45}, '32X39X12': {'min': 43, 'max': 47},
        '28X32X17,5': {'min': 36, 'max': 41},
    },
    'BAG 100GRS': {
        '10X19X05': {'min': 6.00, 'max': 8.50}, '10X25X05': {'min': 7.89, 'max': 11.18},
        '12X25X07': {'min': 7, 'max': 9}, '15X25X07': {'min': 8, 'max': 10},
        '18X30X10': {'min': 23.20, 'max': 26.70}, '22X30X12': {'min': 28.00, 'max': 31.26},
        '22X40X12': {'min': 35.00, 'max': 38.00}, '32X30X12': {'min': 36.00, 'max': 42.00},
        '32X40X12': {'min': 45.00, 'max': 52.00}, '35X45X14': {'min': 54.45, 'max': 61.45},
        '32X45X12': {'min': 50.40, 'max': 56.70}, '32X30X16': {'min': 39.60, 'max': 43.60},
        '28X31X20': {'min': 44.55, 'max': 48.55}, '32X45X16': {'min': 54.45, 'max': 60.45},
        '25X30X9': {'min': 28.00, 'max': 31.50}, '18X25X10': {'min': 20.30, 'max': 24.60},
        '25X25X9': {'min': 24.50, 'max': 28.80}, '29X40X15': {'min': 45.00, 'max': 49.30},
        '25X40X14': {'min': 40.00, 'max': 44.30}, '25X30X14': {'min': 32.00, 'max': 36.30},
        '40X45X14': {'min': 60.50, 'max': 67.50}, '31X31X18': {'min': 44.55, 'max': 50.55},
        '18X35X10': {'min': 24, 'max': 28}, '24X32X14,5': {'min': 29, 'max': 35},
        '24X35X14,5': {'min': 34, 'max': 38}, '31X34X12': {'min': 36, 'max': 42},
        '31X37X12': {'min': 39, 'max': 44}, '32X39X12': {'min': 42, 'max': 46},
        '28X32X17,5': {'min': 35, 'max': 40},
    },
    'BAG 80GRS': {
        '10X19X05': {'min': 5.00, 'max': 7.50}, '10X25X05': {'min': 6.58, 'max': 9.87},
        '12X25X07': {'min': 7, 'max': 9}, '15X25X07': {'min': 8, 'max': 10},
        '18X30X10': {'min': 18.56, 'max': 22.06}, '22X30X12': {'min': 22.40, 'max': 25.66},
        '22X40X12': {'min': 28.00, 'max': 31.00}, '32X30X12': {'min': 28.80, 'max': 34.80},
        '32X40X12': {'min': 36.00, 'max': 43.00}, '35X45X14': {'min': 43.56, 'max': 50.56},
        '32X45X12': {'min': 40.32, 'max': 46.62}, '32X30X16': {'min': 31.68, 'max': 35.68},
        '28X31X20': {'min': 35.64, 'max': 39.64}, '32X45X16': {'min': 43.56, 'max': 49.56},
        '25X30X9': {'min': 22.40, 'max': 25.90}, '18X25X10': {'min': 16.24, 'max': 20.54},
        '25X25X9': {'min': 19.60, 'max': 23.90}, '29X40X15': {'min': 36.00, 'max': 40.30},
        '25X40X14': {'min': 32.00, 'max': 36.30}, '25X30X14': {'min': 25.60, 'max': 29.90},
        '40X45X14': {'min': 48.40, 'max': 55.40}, '31X31X18': {'min': 35.64, 'max': 41.64},
        '18X35X10': {'min': 18, 'max': 23}, '24X32X14,5': {'min': 24, 'max': 28},
        '24X35X14,5': {'min': 26, 'max': 30}, '31X34X12': {'min': 29, 'max': 33},
        '31X37X12': {'min': 31, 'max': 35}, '32X39X12': {'min': 33, 'max': 38},
        '28X32X17,5': {'min': 28, 'max': 34},
    },
    'BAG 70GRS': {
        '10X19X05': {'min': 4.00, 'max': 6.50}, '10X25X05': {'min': 5.26, 'max': 8.55},
        '12X25X07': {'min': 7, 'max': 9}, '15X25X07': {'min': 8, 'max': 10},
        '18X30X10': {'min': 16.24, 'max': 19.74}, '22X30X12': {'min': 19.60, 'max': 22.86},
        '22X40X12': {'min': 24.50, 'max': 27.50}, '32X30X12': {'min': 25.20, 'max': 31.20},
        '32X40X12': {'min': 31.50, 'max': 38.50}, '35X45X14': {'min': 38.12, 'max': 45.12},
        '32X45X12': {'min': 35.28, 'max': 41.58}, '32X30X16': {'min': 27.72, 'max': 31.72},
        '28X31X20': {'min': 31.19, 'max': 35.19}, '32X45X16': {'min': 38.12, 'max': 44.12},
        '25X30X9': {'min': 19.60, 'max': 23.10}, '18X25X10': {'min': 14.21, 'max': 18.51},
        '25X25X9': {'min': 17.15, 'max': 21.45}, '29X40X15': {'min': 31.50, 'max': 35.80},
        '25X40X14': {'min': 28.00, 'max': 32.30}, '25X30X14': {'min': 22.40, 'max': 26.70},
        '40X45X14': {'min': 42.35, 'max': 49.35}, '31X31X18': {'min': 31.19, 'max': 37.19},
        '18X35X10': {'min': 17, 'max': 22}, '24X32X14,5': {'min': 23, 'max': 27},
        '24X35X14,5': {'min': 25, 'max': 29}, '31X34X12': {'min': 28, 'max': 32},
        '31X37X12': {'min': 30, 'max': 34}, '32X39X12': {'min': 32, 'max': 37},
        '28X32X17,5': {'min': 26, 'max': 33},
    },
    'MG 25GRS': {
        '20X30': {'min': 1.40, 'max': 1.60},
        '30X38': {'min': 2.50, 'max': 3.00},
    },
    'RU 32GRS': {
        '20X30': {'min': 1.80, 'max': 2.10},
        '30X38': {'min': 3.50, 'max': 3.80},
    },
    'KRAFT 35GRS': {
        '20X30': {'min': 1.90, 'max': 2.30},
        '30X38': {'min': 3.80, 'max': 4.10},
    },
}


def _descricoes_seed():
    descricoes = set(_SEED_FORMATOS)
    descricoes.update(_SEED_SPEED.keys())
    descricoes.update(_SEED_LARGURA.keys())
    for formatos in _SEED_TOLERANCIAS.values():
        descricoes.update(formatos.keys())
    return sorted(descricoes)


def migrar_formatos_legados(conn=None):
    """
    Insere formatos legados que ainda não existem no cadastro.
    Idempotente: não sobrescreve registros já cadastrados na tela.
    Retorna dict com contagens: inseridos, pulados, erros, tolerancias.
    """
    close = False
    if conn is None:
        conn = get_db_connection()
        close = True

    inseridos = 0
    pulados = 0
    erros = 0
    tolerancias = 0

    try:
        for desc in _descricoes_seed():
            existe = conn.execute(
                "SELECT id FROM formatos_cadastro WHERE descricao = ?", (desc,)
            ).fetchone()
            if existe:
                pulados += 1
                continue

            velocidade = _SEED_SPEED.get(desc)
            largura = _SEED_LARGURA.get(desc)
            if velocidade is None or largura is None:
                logger.warning(
                    "Migração de formato '%s' pulada: velocidade=%s largura=%s",
                    desc, velocidade, largura,
                )
                erros += 1
                continue

            try:
                cur = conn.execute(
                    "INSERT INTO formatos_cadastro (descricao, largura_bobina, velocidade_ideal) "
                    "VALUES (?, ?, ?)",
                    (desc, float(largura), float(velocidade)),
                )
                formato_id = cur.lastrowid
                for papel, mapa in _SEED_TOLERANCIAS.items():
                    tol = mapa.get(desc)
                    if not tol:
                        continue
                    conn.execute(
                        "INSERT INTO formato_tolerancias (formato_id, papel, min_kg, max_kg) "
                        "VALUES (?, ?, ?, ?)",
                        (formato_id, papel, float(tol['min']), float(tol['max'])),
                    )
                    tolerancias += 1
                inseridos += 1
            except Exception:
                logger.exception("Erro ao migrar formato '%s'", desc)
                erros += 1

        if close:
            conn.commit()
    finally:
        if close:
            conn.close()

    resultado = {
        'inseridos': inseridos,
        'pulados': pulados,
        'erros': erros,
        'tolerancias': tolerancias,
    }
    if inseridos or erros:
        logger.info("Migração de formatos legados: %s", resultado)
    return resultado
