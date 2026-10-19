# Importa a função create_app do pacote app, responsável por criar a aplicação Flask
from app import create_app

# Cria uma instância da aplicação Flask usando a factory function
app = create_app()

# Verifica se o arquivo está sendo executado diretamente
if __name__ == "__main__":
    # Importa e executa a função para inicializar o banco de dados (produção)
    from app.models import inicializar_banco
    inicializar_banco()
    # Cria tabelas de custo se não existirem
    from database.connection import criar_tabelas_custo
    criar_tabelas_custo()
    from app.migracoes import aplicar_migracoes_pendentes
    print(f"[migracoes] Banco de dados: {aplicar_migracoes_pendentes()} (detalhes em logs/app.log)")
    
    # Usa Waitress para produção ou Flask dev server para desenvolvimento
    import os
    from app.config import SERVER_PORT
    debug_mode_check = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    is_waitress = os.getenv('FLASK_ENV') == 'production' or os.getenv('USE_WAITRESS', '').lower() == 'true'
    # Com o reloader do Flask (debug=True), o processo "pai" apenas observa
    # arquivos; só o processo filho (WERKZEUG_RUN_MAIN=true) deve rodar o
    # backup, senão ele dispara em dobro a cada reload.
    if is_waitress or not debug_mode_check or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        from app.backup import iniciar_backup_automatico
        iniciar_backup_automatico()

    if is_waitress:
        from waitress import serve
        print(f"Iniciando servidor com Waitress na porta {SERVER_PORT}...")
        serve(app, host="0.0.0.0", port=SERVER_PORT, threads=8, channel_timeout=120)
    else:
        # Modo desenvolvimento/rede local com Flask dev server.
        # Mantido em 0.0.0.0 propositalmente (uso documentado em
        # INSTRUCOES_ACESSO_REDE.md para acesso de outros PCs da fábrica).
        # ATENÇÃO: debug=True expõe o debugger interativo do Werkzeug na rede
        # (risco de execução remota de código). Defina FLASK_DEBUG=false para
        # desativar sem mudar este arquivo.
        app.run(host="0.0.0.0", port=SERVER_PORT, debug=debug_mode_check)
