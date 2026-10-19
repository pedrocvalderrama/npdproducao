# Instruções para Executar com Waitress

## Instalação das Dependências

Instale as dependências necessárias:

```bash
pip install -r requirements.txt
```

## Formas de Executar

### Opção 1: Usando o arquivo wsgi.py (Recomendado para produção)

```bash
python wsgi.py
```

Isso iniciará o servidor Waitress na porta 8080, acessível em todas as interfaces (0.0.0.0).

### Opção 2: Usando o app.py com variável de ambiente

Para forçar o uso do Waitress mesmo no app.py:

```bash
# Windows PowerShell
$env:USE_WAITRESS="true"
python app.py

# Windows CMD
set USE_WAITRESS=true
python app.py

# Linux/macOS
export USE_WAITRESS=true
python app.py
```

Ou definir como produção:

```bash
# Windows PowerShell
$env:FLASK_ENV="production"
python app.py

# Linux/macOS
export FLASK_ENV=production
python app.py
```

### Opção 3: Executar diretamente com Waitress via linha de comando

```bash
waitress-serve --host=0.0.0.0 --port=8080 wsgi:application
```

## Configuração do Servidor

O servidor está configurado para:
- **Host**: 0.0.0.0 (todas as interfaces de rede)
- **Porta**: 8080
- **Servidor**: Waitress (WSGI puro para produção)

## Vantagens do Waitress

- Servidor WSGI puro e eficiente
- Adequado para produção
- Suporta múltiplas requisições simultâneas
- Funciona bem em Windows, Linux e macOS
- Não requer configuração adicional de servidor web

## Acessar a Aplicação

Após iniciar o servidor, acesse:
- **URL Local**: http://localhost:8080
- **URL Rede**: http://[IP_DO_SERVIDOR]:8080

