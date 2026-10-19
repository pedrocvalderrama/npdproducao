"""
Utilitários de formatação (datas, etc)
"""
from datetime import datetime


def formatar_data_br(data_iso):
    """Converte data ISO para formato brasileiro DD/MM/YYYY."""
    if data_iso:
        try:
            if ' ' in data_iso:
                data_iso = data_iso.split(' ')[0]
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y%m%d'):
                try:
                    return datetime.strptime(data_iso, fmt).strftime('%d/%m/%Y')
                except ValueError:
                    continue
            return data_iso
        except Exception:
            return data_iso
    return ""


def formatar_data_iso(data_br):
    """Converte data brasileira para formato ISO YYYY-MM-DD."""
    if data_br:
        try:
            if len(data_br.split('-')) == 3:
                return data_br
            if '/' in data_br:
                return datetime.strptime(data_br, '%d/%m/%Y').strftime('%Y-%m-%d')
        except Exception:
            return None
    return None


def obter_data_atual_iso():
    """Retorna a data atual no formato ISO YYYY-MM-DD."""
    return datetime.now().strftime('%Y-%m-%d')
