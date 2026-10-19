"""
Funções auxiliares compartilhadas entre as rotas para ler valores de
formulário com segurança (tratando campos vazios/ausentes).

Extraído de app/routes.py na Fase 3 da auditoria de otimização, para poder
ser reaproveitado pelos diferentes módulos de rota sem duplicação.
"""


def safe_get_int(form_data, key, default=0):
    """Retorna um inteiro do formulário ou valor padrão se vazio."""
    value = form_data.get(key, '')
    if value == '' or value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_get_float(form_data, key, default=0.0):
    """Retorna um float do formulário ou valor padrão se vazio."""
    value = form_data.get(key, '')
    if value == '' or value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_get_str(form_data, key, default=None):
    """Retorna uma string do formulário ou valor padrão se vazio."""
    value = form_data.get(key, '')
    if value == '' or value is None:
        return default if default is not None else ''
    result = str(value).strip()
    return result if result else (default if default is not None else '')
