# NPD - Sistema Integrado de Produção e Custos

Sistema unificado para controle de produção industrial e cálculo de custos, desenvolvido em Flask. Inclui lançamento de produção, relatórios, análises e gestão de custos (papel e operacionais).

> **Documentação completa:** o [MANUAL.md](MANUAL.md) é o manual oficial do sistema — explica toda a lógica de negócio (fórmulas, fluxos, telas), a arquitetura técnica e todas as formas de rodar e manter o sistema. Este README traz um resumo operacional.

## Estrutura do Projeto

```
.
├── app.py                # Ponto de entrada da aplicação
├── app/                  # Módulos do backend
│   ├── __init__.py       # Inicialização do app Flask
│   ├── routes.py         # Rotas de produção
│   ├── models.py         # Banco de dados e inicialização
│   ├── business.py       # Lógica de negócio
│   ├── charts.py         # Geração de gráficos
│   ├── config.py         # Constantes e configurações
│   └── custo/            # Módulo de custos
│       ├── routes/       # Rotas (relatório, custo papel, custos operacionais)
│       ├── services/     # Lógica de negócio de custos
│       └── utils/        # Formatadores
├── database/             # Conexão e tabelas de custo
├── templates/            # Templates HTML (Jinja2)
│   ├── base.html         # Layout unificado com navegação
│   ├── index.html
│   ├── historico.html
│   ├── custos_papel/
│   ├── custos_operacionais/
│   └── relatorio/
├── static/
├── dados_producao.db     # Banco de dados SQLite (compartilhado)
└── backup/
```

## Instalação

1. **Clone o repositório:**
   ```bash
   git clone <seu-repo>
   cd <seu-repo>
   ```

2. **Crie um ambiente virtual (opcional, mas recomendado):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate    # Windows
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure o caminho do banco de dados:**
   - O caminho é definido em `app/config.py` na variável `DB_NAME` (fixo: `dados_producao.db` na raiz do projeto). Não há suporte a sobrescrever via variável de ambiente atualmente.

5. **Variáveis de ambiente opcionais:**
   - `SECRET_KEY`: chave de sessão do Flask. Se não definida, é gerada automaticamente e salva em `.secret_key` na raiz do projeto (arquivo local, fora do Git), reaproveitada a cada início — evita deslogar todos os operadores a cada reinício do servidor. Defina a variável de ambiente para usar um valor fixo controlado por você (ex.: em produção com múltiplas instâncias).
   - `FLASK_DEBUG`: `false` desativa o modo debug do servidor de desenvolvimento (padrão: `true`).
   - `FLASK_ENV=production` ou `USE_WAITRESS=true`: faz `app.py` rodar com Waitress em vez do servidor de desenvolvimento do Flask.
   - `ADMIN_PASSWORD`: fixa a senha do usuário `admin` criado automaticamente no primeiro início (veja seção "Login" abaixo). Sem essa variável, uma senha aleatória é gerada e impressa uma única vez no console.

## Execução

1. **Inicialize o banco de dados (apenas na primeira vez):**
   - O banco será criado automaticamente ao rodar o app.

2. **Execute a aplicação:**
   ```bash
   python app.py
   ```
   - O servidor estará disponível em [http://localhost:8082](http://localhost:8082) (porta definida em `app/config.py`, `SERVER_PORT`)

3. **Para produção:**
   - O projeto já suporta Waitress (WSGI). Para rodar em produção:
   ```bash
   python app.py
   ```
   - Ou use um servidor WSGI de sua preferência.

## Login

O sistema agora exige login. Uma conta é criada automaticamente para cada operador
listado em `app/config.py` (`OPERADORES_SOS`, `OPERADORES_IMPRESSORA`, `OPERADORES_ROBO`):
- **Usuário:** nome do operador sem acentos/maiúsculas (ex.: `JOSÉ` → `jose`).
- **Senha inicial:** igual ao usuário. Cada pessoa deve trocar a própria senha em
  **"Trocar senha"** (link com o nome dela, no topo da tela) assim que possível.

Uma conta `admin` também é criada na primeira execução; a senha inicial é gerada
aleatoriamente e impressa uma única vez no console ao iniciar o servidor (procure
por `[auth] Usuário 'admin' criado...`). Para fixar uma senha de administrador,
defina a variável de ambiente `ADMIN_PASSWORD` antes da primeira execução.

**Para adicionar um novo operador:** inclua o nome nas listas de `app/config.py`
e reinicie o servidor — a conta é criada automaticamente no próximo início.

### Papéis de acesso

Cada usuário tem um papel que define o que ele pode acessar:

| Papel | Acesso |
|---|---|
| **Inicial** | Produção e Custos (inclusive lançar custo de um pedido, dentro de Custos). **Não** vê nem acessa as páginas Pedidos e Movimento. |
| **Gerente** | Acesso completo a todas as páginas, incluindo Pedidos e Movimento. |
| **Admin** | Acesso completo + pode cadastrar/gerenciar usuários em **Usuários** (menu superior). |

Operadores do chão de fábrica são criados automaticamente com papel **Inicial**.
O `admin` é criado com papel **Admin**.

### Cadastrar usuários independentes de operador

Pessoas de fora do chão de fábrica (financeiro, diretoria, etc.) podem ter uma
conta própria, sem depender das listas de operadores. Um usuário com papel
**Admin** acessa **Usuários** no menu superior e cadastra: login, nome, senha
inicial e papel de acesso. Nessa mesma tela também é possível redefinir a
senha de qualquer usuário e ativar/desativar contas.

## Funcionalidades

### Produção
- **Lançamento:** Cadastro de dados de produção com cálculo automático de métricas.
- **Histórico:** Filtros avançados, ordenação, exportação para Excel.
- **OF-Refugo:** Relatório simplificado de OFs com refugos.
- **Comparação Quantidade:** Comparação entre comanda, impressora e SOS.
- **Comparativo Mensal:** Métricas mês a mês.
- **Análise:** Tabelas de resumo por máquina, operador, formato e papel.

### Custos
- **Relatório de Custo OFs:** Relatório de custos por OF com filtro por período.
- **Custo Papel:** Cadastro de custos por kg de papel.
- **Custos Adicionais:** Configuração de despesas (TINTA, COLA, ALÇA, etc.).

## Dicas e Customização
- Para adicionar operadores, máquinas ou formatos, edite `app/config.py`.
- Para customizar estilos, edite os arquivos em `static/css/`.
- As rotas ficam organizadas em `app/routes/` (um arquivo por área: `producao.py`,
  `historico.py`, `pedidos_movimento.py`, `listagens.py`, `analise.py`), todas
  registradas no mesmo blueprint `main` — para adicionar uma rota nova, escolha
  o arquivo mais próximo do assunto ou crie um novo módulo e importe-o em
  `app/routes/__init__.py`.
- Regras de negócio de persistência (cálculo de campos, INSERT/UPDATE) ficam em
  `app/services/` — ex.: `producao_service.py` centraliza o que antes estava
  duplicado entre `/lancar` e `/editar`.

## Testes automatizados

```
.\venv\Scripts\python.exe -m pytest tests/ -v
```

A suíte usa um banco SQLite temporário e isolado (nunca toca no
`dados_producao.db` real). Rode-a antes de qualquer alteração maior nas rotas
ou nos services, para garantir que login, controle de acesso por papel e o
ciclo lançar/editar/excluir continuam funcionando.

## Migrações de banco de dados (Alembic)

O schema é controlado por versão com [Alembic](https://alembic.sqlalchemy.org/)
a partir da revisão `baseline schema atual` (que corresponde ao schema já
existente hoje, criado por `inicializar_banco()`). A partir de agora, **toda
mudança de schema deve ser uma nova revisão do Alembic**, em vez de outro
`ALTER TABLE` manual dentro de `app/models.py`.

- Criar uma nova migração: `.\venv\Scripts\python.exe -m alembic revision -m "descrição da mudança"`,
  depois editar o arquivo gerado em `migrations/versions/` com `op.add_column(...)` etc.
- Aplicar migrações pendentes: `.\venv\Scripts\python.exe -m alembic upgrade head`
- Ver a revisão atual do banco: `.\venv\Scripts\python.exe -m alembic current`
- Um banco novo (instalação limpa) já sai com o schema completo ao rodar
  `alembic upgrade head` (a revisão baseline reaproveita `inicializar_banco()`).
- **Automático ao iniciar o servidor** (`wsgi.py` / `app.py`, via
  `app/migracoes.py`): se o banco nunca passou pelo Alembic, ele é marcado na
  revisão baseline; havendo revisões pendentes, é feito um backup
  (`backup/dados_producao_antes_migracao_<data>.db`) e todas são aplicadas.
  O resultado fica em `logs/app.log`. Se algo falhar, o erro é registrado e o
  servidor sobe mesmo assim. Ou seja: basta copiar o projeto atualizado para o
  servidor (sem sobrescrever o `dados_producao.db` de lá) e reiniciar.

## Navegação sem reload completo com htmx (Fase 4 da auditoria de otimização)

As telas de listagem com filtros/ordenação/paginação (Histórico, Pedidos,
Movimento, OF-Refugo e Comparação de Quantidade) usam a biblioteca
[htmx](https://htmx.org) (servida localmente em
`static/js/vendor/htmx.min.js`, sem CDN) para trocar apenas a tabela e a
barra de paginação, em vez de recarregar a página inteira a cada clique em
"Filtrar", em um cabeçalho de coluna ou em "Próxima/Anterior".

Como funciona, usando o Histórico como exemplo:

- O formulário de filtros, o link "Limpar Filtros", os links de ordenação do
  cabeçalho da tabela e os links de paginação ganham os atributos
  `hx-get="<mesma URL do href>" hx-target="#historico-resultado" hx-push-url="true"`.
  O htmx intercepta o clique, faz a requisição via `fetch` (mandando o header
  `HX-Request: true`) e substitui o conteúdo de `#historico-resultado`
  pela resposta, atualizando a URL do navegador (histórico/voltar funcionam
  normalmente) sem recarregar `<head>`, menu, CSS e JS de novo.
- Cada rota (`app/routes/historico.py`, `pedidos_movimento.py`,
  `listagens.py`) monta o mesmo contexto de sempre e decide o que renderizar
  checando `request.headers.get('HX-Request') == 'true'`: se vier do htmx,
  devolve só o fragmento (`templates/partials/<tela>_resultado.html`, com a
  barra de paginação + tabela); caso contrário, devolve a página completa
  (que inclui esse mesmo fragmento via `{% include %}`), garantindo que os
  dois caminhos renderizam exatamente o mesmo HTML de resultado e nunca saem
  de sincronia.
- Como as tabelas têm colunas "coladas" à esquerda (`sticky-left`) cuja
  posição é calculada em JavaScript, o cálculo foi extraído para uma função
  nomeada e é executado tanto no `DOMContentLoaded` quanto no evento
  `htmx:afterSwap` (disparado depois de cada troca), para continuar correto
  após navegar via htmx.
- Exportar Excel e o botão "Atualizar Banco de Dados" continuam sendo
  navegação/POST normal (sem htmx), pois um deles baixa um arquivo e o outro
  precisa do redirect com flash message de resultado.

## API JSON para integrações (Fase 4 da auditoria de otimização)

Além das telas HTML, o sistema expõe uma API JSON somente leitura em
`/api/v1/`, pensada para integrações futuras (um BI, uma automação, outro
sistema da fábrica) sem precisar simular login por formulário. Nenhuma rota
da API faz INSERT/UPDATE/DELETE.

- **Autenticação:** header `X-API-Key: <chave>`, ou a sessão de login normal
  (útil para testar as rotas direto do navegador). A chave é gerada e
  persistida em `.api_key` na raiz do projeto (fora do versionamento, mesmo
  esquema do `.secret_key`), ou pode ser fixada via variável de ambiente
  `API_KEY` (recomendado em produção). Um administrador consulta/regenera a
  chave em `/admin/api-key`.
- **Paginação:** todas as listagens aceitam `?page=` e `?per_page=` (máx.
  500) e devolvem `{"data": [...], "page", "per_page", "total", "total_paginas"}`.
- **Índice autoexplicativo:** `GET /api/v1/` lista todas as rotas disponíveis
  com seus filtros.

Endpoints disponíveis (implementação em `app/routes/api.py`):

| Rota | Descrição |
| --- | --- |
| `GET /api/v1/producao` | Lançamentos de produção. Filtros: `num_of`, `servico` (contém), `operador`, `data`. |
| `GET /api/v1/producao/<id>` | Um lançamento específico. |
| `GET /api/v1/pedidos` | Pedidos importados (CSV Sisplan). Filtros: `pedido`, `fantasia`, `cidade`, `uf`, `grupo` (contém). |
| `GET /api/v1/movimento` | Pedidos com custo/margem calculados (mesmos filtros de `/pedidos`). |
| `GET /api/v1/custos/papel` | Custo por kg cadastrado por tipo de papel. |
| `GET /api/v1/custos/operacionais` | Despesas operacionais cadastradas. |
| `GET /api/v1/resumo-mensal?ano=AAAA` | Quantidade produzida e refugo (kg) totais por mês. |

Exemplo:

```bash
curl -H "X-API-Key: <chave>" http://SERVIDOR:8082/api/v1/producao?per_page=10
```

## Logs (Fase 4 da auditoria de otimização)

A aplicação grava logs em arquivo (além do console), essencial quando o
servidor roda como serviço do Windows (sem janela de console visível):

- **`logs/app.log`**: mensagens da aplicação (avisos, erros, exceções não
  tratadas com stack trace completo) e de módulos internos como o backup
  automático (`app/backup.py`).
- **`logs/access.log`**: uma linha por requisição HTTP, no formato
  `metodo=GET rota=/historico status=200 duracao_ms=12.3 usuario=admin ip=...`
  — fácil de filtrar com `Select-String`/`grep`.
- Ambos os arquivos rotacionam automaticamente (5 MB por arquivo, últimos 5
  mantidos) via `RotatingFileHandler` da própria stdlib do Python — sem
  dependência nova, configurado em `app/logging_config.py`.
- Nível configurável via variável de ambiente `LOG_LEVEL` (padrão `INFO`;
  use `DEBUG` para investigar um problema específico). Pasta configurável
  via `LOG_DIR` (padrão: `logs/` na raiz do projeto; durante os testes
  automatizados, os logs vão para a pasta temporária do banco de teste, não
  para `logs/` da raiz).

## Deploy como serviço do Windows com NSSM (Fase 4 da auditoria de otimização)

Rodar o `iniciar_servidor.bat` manualmente exige deixar uma janela de
console aberta e reiniciar à mão se o servidor cair ou o Windows reiniciar.
Para produção, a pasta `deploy/` traz scripts que instalam o NPD como
**serviço do Windows** usando o [NSSM](https://nssm.cc/) — ele fica rodando
em segundo plano, inicia automaticamente com o Windows e reinicia sozinho
se o processo cair.

1. Baixe o NSSM em <https://nssm.cc/download> (pacote `win64`) e copie
   `nssm.exe` para dentro da pasta `deploy/` do projeto (ou para qualquer
   pasta já no `PATH` do sistema).
2. Garanta que o ambiente virtual já existe (`venv\Scripts\python.exe`) —
   se nunca rodou o projeto nesta máquina, execute `iniciar_servidor.bat`
   uma vez, deixe instalar as dependências e pare com `CTRL+C`.
3. Abra um **PowerShell como Administrador**, vá até `deploy\` e instale:
   ```powershell
   cd "deploy"
   .\instalar_servico.ps1
   ```
   Isso cria o serviço `NPD-Producao` (nome customizável via
   `-ServiceName`), configurado para iniciar automaticamente com o Windows,
   reiniciar em caso de falha, e gravar a saída do processo em
   `logs\service_stdout.log`/`service_stderr.log` (com rotação própria do
   NSSM) — útil para capturar erros de inicialização, complementando
   `app.log`/`access.log` descritos acima.
4. Verificar status e ver as últimas linhas dos logs a qualquer momento:
   ```powershell
   .\status_servico.ps1
   ```
5. Para remover o serviço (ex.: antes de reinstalar em outra pasta):
   ```powershell
   .\desinstalar_servico.ps1
   ```

Comandos úteis do Windows para gerenciar o serviço diretamente (sem o
NSSM): `Start-Service NPD-Producao`, `Stop-Service NPD-Producao`,
`Restart-Service NPD-Producao`, ou pela GUI em `services.msc`.

## Licença

Este projeto é privado e de uso interno. 