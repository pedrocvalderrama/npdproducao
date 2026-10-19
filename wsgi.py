"""
Arquivo WSGI para produção usando Waitress
"""
from app import create_app
from app.backup import iniciar_backup_automatico
from app.models import inicializar_banco

# Inicializa o banco de dados
inicializar_banco()

# Backup automático diário (roda em produção real via WSGI)
iniciar_backup_automatico()

# Cria a aplicação Flask
application = create_app()

# Aplica migrações pendentes do Alembic (tabelas novas) no banco existente
from app.migracoes import aplicar_migracoes_pendentes
print(f"[migracoes] Banco de dados: {aplicar_migracoes_pendentes()} (detalhes em logs/app.log)")

if __name__ == "__main__":
    # Para desenvolvimento, pode rodar diretamente
    from waitress import serve
    from app.config import SERVER_PORT
    serve(application, host="0.0.0.0", port=SERVER_PORT, threads=8, channel_timeout=120)

