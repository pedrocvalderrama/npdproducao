"""
Módulo de custos - integrado ao NPD
"""
from .routes.custos_papel import bp as custos_papel_bp
from .routes.custos_operacionais import bp as custos_operacionais_bp
from .routes.relatorio import bp as relatorio_bp

__all__ = ['custos_papel_bp', 'custos_operacionais_bp', 'relatorio_bp']
