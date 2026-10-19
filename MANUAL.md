# Manual Oficial do Sistema NPD

**Sistema Integrado de Produção e Custos**

| | |
|---|---|
| **Documento** | Manual técnico e operacional |
| **Versão do documento** | 1.0 |
| **Data** | Agosto de 2026 |
| **Tecnologia** | Python 3.12 · Flask · SQLite · Waitress |
| **Público-alvo** | Operadores, gerentes, administradores e desenvolvedores |

---

## Sumário

1. [Visão geral do sistema](#1-visão-geral-do-sistema)
2. [Conceitos do domínio (glossário)](#2-conceitos-do-domínio-glossário)
3. [Arquitetura técnica](#3-arquitetura-técnica)
4. [Banco de dados](#4-banco-de-dados)
5. [Autenticação e níveis de acesso](#5-autenticação-e-níveis-de-acesso)
6. [Fluxo de produção: do lançamento ao relatório](#6-fluxo-de-produção-do-lançamento-ao-relatório)
7. [Telas do sistema, uma a uma](#7-telas-do-sistema-uma-a-uma)
8. [Fórmulas e cálculos detalhados](#8-fórmulas-e-cálculos-detalhados)
9. [Módulo de Custos](#9-módulo-de-custos)
10. [Movimento: cálculo de custo por pedido](#10-movimento-cálculo-de-custo-por-pedido)
11. [API JSON para integrações](#11-api-json-para-integrações)
12. [Frontend: HTMX e Chart.js](#12-frontend-htmx-e-chartjs)
13. [Logs e diagnóstico](#13-logs-e-diagnóstico)
14. [Como rodar o sistema](#14-como-rodar-o-sistema)
15. [Testes automatizados](#15-testes-automatizados)
16. [Manutenção: backups e migrações de banco](#16-manutenção-backups-e-migrações-de-banco)
17. [Solução de problemas (troubleshooting)](#17-solução-de-problemas-troubleshooting)
18. [Apêndice A — Variáveis de ambiente](#apêndice-a--variáveis-de-ambiente)
19. [Apêndice B — Arquivos gerados em tempo de execução](#apêndice-b--arquivos-gerados-em-tempo-de-execução)

---

## 1. Visão geral do sistema

O **NPD** é um sistema web interno para controle de **produção industrial de embalagens de papel** (sacolas SOS e cartuchos) e para **apuração de custos** por ordem de fabricação e por pedido de venda.

Ele cobre o ciclo completo do chão de fábrica ao escritório:

1. **Lançamento de produção**: o operador registra cada Ordem de Fabricação (OF) com quantidades, refugos, tempos e horários de cada etapa (Impressora, SOS, Robô de alça, Inspeção Final).
2. **Cálculo automático de métricas**: no momento do lançamento, o sistema calcula percentual de refugo, velocidade, eficiência, consumo de papel e perdas — o operador não precisa fazer conta nenhuma.
3. **Consultas e análises**: telas de histórico completo, refugo por OF, comparação de quantidades entre etapas, comparativo mensal com metas e gráfico.
4. **Custos**: cadastro do custo por kg de cada papel e das despesas operacionais unitárias, com relatório que cruza esses cadastros com a produção lançada e calcula o custo final de cada OF.
5. **Comercial**: importação dos pedidos do sistema Sisplan (CSV) e a tela Movimento, que atribui a cada pedido de venda um custo estimado a partir das OFs produzidas.
6. **Integrações**: API JSON somente leitura para BI, automações ou outros sistemas.

O sistema roda em um único servidor Windows na rede local da fábrica, na porta **8082**, e é acessado pelo navegador de qualquer máquina da rede (`http://IP_DO_SERVIDOR:8082`).

---

## 2. Conceitos do domínio (glossário)

| Termo | Significado |
|---|---|
| **OF (Nº OF)** | Ordem de Fabricação. Identificador único de cada trabalho de produção. É a "chave" do lançamento: relançar a mesma OF **atualiza** o registro existente em vez de duplicar. |
| **SOS** | Máquina que forma o saco/sacola de papel (SOS 1 a SOS 4). "Quantidade SOS" é a produção boa dessa etapa. |
| **Impressora / Flexo** | Impressora flexográfica que imprime a bobina antes da formação. "Flexo" e "Impressora" são usados como sinônimos nos campos de refugo. |
| **Pré-impresso** | Papel que já chega impresso (não passa pela impressora da fábrica). É um dos "Tipos de Impressão" (SOS ou Pré-impresso). |
| **Robô (Robô Alça)** | Equipamento que aplica alças nas sacolas. Gera refugo próprio, contado em **peças**. |
| **Inspeção Final** | Etapa de conferência final. Gera a "Quantidade Inspeção Final" (peças boas aprovadas) e o "Refugo Inspeção Final" (peças). |
| **Milheiro (Peso Milheiro)** | Peso, em kg, de 1.000 unidades do produto. É o fator de conversão entre **peças** e **kg** usado em quase todos os cálculos: `peso de 1 peça = milheiro ÷ 1000`. |
| **Refugo** | Material perdido/descartado. Existem refugos em **kg** (Flexo, Pré-impresso, SOS, Acerto Flexo, Acerto SOS) e refugos em **peças** (Robô, Inspeção Final). |
| **Acerto** | Tempo/material gasto para preparar (ajustar) a máquina antes da produção. Tem refugo próprio (Refugo Acerto Flexo / Acerto SOS) e tempo próprio (Início/Fim Acerto). |
| **Quantidade Comanda** | Quantidade solicitada na comanda/ordem (o que deveria ser produzido). |
| **Clichês** | Chapas de impressão flexográfica. A quantidade de clichês define o tempo ideal de acerto. |
| **Consumo Útil** | Papel (kg) efetivamente convertido em produto bom aprovado na inspeção. |
| **Consumo Total** | Consumo Útil + todas as perdas em kg. É o papel total gasto na OF. |
| **Pedido (Sisplan)** | Pedido de venda importado do sistema comercial Sisplan via arquivo CSV. Ligado à produção pelo campo "Número do Pedido" da OF. |
| **SACOLA / CARTUCHO** | Os dois tipos de produto. Afetam o cálculo de custo: sacolas incluem a despesa de ALÇA; cartuchos usam apenas a despesa TINTA. |

---

## 3. Arquitetura técnica

### 3.1 Stack

| Camada | Tecnologia | Papel |
|---|---|---|
| Linguagem | Python 3.12 | Backend |
| Framework web | Flask | Rotas, templates, sessões |
| Servidor de produção | Waitress | Servidor WSGI multithread para Windows |
| Banco de dados | SQLite (modo WAL) | Arquivo único `dados_producao.db` |
| Migrações | Alembic + SQLAlchemy | Versionamento do schema |
| Templates | Jinja2 | HTML renderizado no servidor |
| Interatividade | HTMX (local) | Filtros/paginação sem reload completo |
| Gráficos | Chart.js (local) | Gráfico do Comparativo Mensal no navegador |
| Dados/Excel | pandas + xlsxwriter | Exportações para Excel |
| Autenticação | Flask-Login + Flask-WTF | Login, sessões e proteção CSRF |
| Testes | pytest | Suíte de regressão (25+ testes) |

Nenhuma biblioteca é carregada de CDN: `htmx.min.js` e `chart.umd.min.js` são servidos localmente de `static/js/vendor/`, então o sistema funciona sem acesso à internet.

### 3.2 Estrutura de pastas

```
NPD/
├── app.py                     # Entrada para desenvolvimento (Flask dev server)
├── wsgi.py                    # Entrada para produção (Waitress)
├── requirements.txt           # Dependências Python
├── alembic.ini                # Configuração do Alembic (migrações)
├── dados_producao.db          # Banco SQLite (criado na primeira execução)
├── sisplanpedidos.csv         # Arquivo de pedidos exportado do Sisplan
│
├── app/                       # Código do backend
│   ├── __init__.py            # create_app(): monta a aplicação, registra tudo
│   ├── config.py              # Constantes: operadores, máquinas, formatos,
│   │                          #   velocidades/refugos ideais, porta, caminhos
│   ├── models.py              # Conexão SQLite (WAL) e criação do schema
│   ├── business.py            # Regras de negócio puras (fórmulas de métricas)
│   ├── utils.py               # Helpers de leitura segura de formulários
│   ├── auth.py                # Login, papéis (roles), gestão de usuários
│   ├── api_auth.py            # Chave da API JSON (X-API-Key)
│   ├── backup.py              # Backup automático diário do banco
│   ├── logging_config.py      # Logs em arquivo (app.log / access.log)
│   ├── pedidos.py             # Importação e listagem de pedidos (CSV Sisplan)
│   ├── movimento.py           # Cálculo de custo por pedido (tela Movimento)
│   │
│   ├── routes/                # Rotas HTTP (blueprint principal "main")
│   │   ├── producao.py        #   Lançamento: /, /buscar-of, /lancar, /editar...
│   │   ├── historico.py       #   /historico (+ exportação Excel)
│   │   ├── listagens.py       #   /of-refugo, /comparacao-quantidade
│   │   ├── analise.py         #   /comparativo-mensal, /analise
│   │   ├── pedidos_movimento.py #  /pedidos, /movimento
│   │   └── api.py             #   API JSON /api/v1/... (blueprint "api")
│   │
│   ├── services/
│   │   └── producao_service.py # Persistência do lançamento (INSERT/UPDATE)
│   │
│   └── custo/                 # Módulo de custos (blueprints próprios)
│       ├── routes/            #   /custo, /custos-papel, /custos-operacionais
│       ├── services/          #   Cálculo do relatório de custo
│       └── utils/             #   Formatadores (datas, números PT-BR)
│
├── database/                  # Conexão legada (delega para app/models.py)
├── migrations/                # Migrações Alembic (baseline + futuras)
├── templates/                 # HTML Jinja2 (partials/ = fragmentos HTMX)
├── static/                    # CSS, JS, imagens (js/vendor = htmx, chart.js)
├── tests/                     # Suíte pytest (conftest + testes)
├── deploy/                    # Scripts de instalação como serviço Windows
├── logs/                      # app.log, access.log (rotação automática)
└── backup/                    # Backups diários do banco (últimos 30 dias)
```

### 3.3 Fluxo de uma requisição

1. O navegador chama, por exemplo, `GET /historico`.
2. O hook global `before_request` (em `app/__init__.py`) verifica:
   - Se a rota é pública (`/login`, arquivos estáticos) → passa direto.
   - Se é rota da API (`/api/v1/...`) → aceita header `X-API-Key` válido **ou** sessão de login; caso contrário devolve `401` em JSON.
   - Para as demais rotas → exige login; depois verifica se o **papel** do usuário pode acessar aquele endpoint (ver seção 5). Sem permissão, redireciona para a tela inicial com aviso.
3. A rota (ex.: `app/routes/historico.py`) consulta o banco via `get_db_connection()` (SQLite em modo WAL, timeout de 15 s), aplica filtros/ordenação/paginação e monta o contexto.
4. Se a requisição veio do HTMX (header `HX-Request: true`), a rota renderiza **apenas o fragmento** da tabela (`templates/partials/..._resultado.html`); senão, renderiza a página completa.
5. O hook `after_request` grava uma linha estruturada em `logs/access.log` (método, rota, status, duração, usuário, IP).

---

## 4. Banco de dados

### 4.1 Visão geral

O banco é um **arquivo SQLite único** (`dados_producao.db` na raiz do projeto), adequado ao perfil de uso do sistema: uma máquina servidora, escritas pouco frequentes (lançamentos manuais), leituras dominantes.

Duas medidas de robustez estão ativas em toda conexão (`app/models.py`):

- **`PRAGMA journal_mode=WAL`** — permite leituras simultâneas enquanto uma escrita está em andamento (evita travamentos com vários usuários).
- **`timeout=15`** — se o banco estiver momentaneamente ocupado, a conexão espera até 15 s em vez de falhar imediatamente com "database is locked".

### 4.2 Tabelas

| Tabela | Conteúdo | Criada por |
|---|---|---|
| `producao` | Um registro por OF, com ~70 colunas: identificação (num_of, serviço, pedido, papel, formato, tipo), quantidades por etapa, refugos (kg e peças), horários (acerto e produção, até 4 dias por etapa), métricas calculadas (refugo %, eficiência, velocidade, consumo, perdas) e observações. | `inicializar_banco()` |
| `metas_mensais` | Meta de quantidade por ano/mês (única por par ano+mês), usada no Comparativo Mensal. | `inicializar_banco()` |
| `lancamento_diario` | Aba "Lançamento Diário": uma linha por equipamento (SOS 1–4, IMPRESSORA, ROBO, RESMADEIRA, GUILHOTINA) e data, com quantidade (no ROBO, sacolas + `quantidade_alcas`), problemas, soluções, observação e usuário. Isolada: não entra em nenhum cálculo das outras telas. | Alembic `a7c3d91e2b40` |
| `metas_lancamento_diario` | Metas mensais do bloco "Meta do Mês" (tela Display Diário), por grupo: SOS (soma SOS 1–4), IMPRESSORA e ROBO (sacolas). Única por ano+mês+grupo. Separada de `metas_mensais`; só é comparada com `lancamento_diario`. | Alembic `b3e8f5a1c2d7` |
| `pedidos` | Pedidos importados do CSV Sisplan (pedido, fantasia, emissão, entrega, medida, grupo, quantidades, valores, cidade, UF, representante...). Importação com deduplicação. | `inicializar_tabela_pedidos()` |
| `custo_papel` | Custo por kg cadastrado para cada tipo de papel. | módulo de custos |
| `custo_operacional` | Despesas operacionais unitárias (por peça produzida), ex.: ALÇA, TINTA, energia. | módulo de custos |
| `usuarios` | Usuários do sistema: login, nome, hash da senha, papel (role), ativo. | `inicializar_tabela_usuarios()` |

Índices criados para acelerar filtros e ordenações mais usados: `producao(num_of)`, `producao(data)`, `producao(numero_pedido)` e `pedidos(pedido)`.

### 4.3 Evolução do schema

Historicamente, o schema evoluiu com `ALTER TABLE ... ADD COLUMN` idempotentes dentro de `inicializar_banco()` (por isso a função é longa — cada `try/except` é uma coluna adicionada ao longo do tempo). A partir da adoção do **Alembic**, a regra é:

> **Toda mudança nova de schema deve ser uma revisão do Alembic** (`migrations/versions/`), não mais um `ALTER TABLE` manual em `models.py`.

A revisão *baseline* (`fe480f523c17`) reproduz o schema completo atual; um banco novo sai pronto com `alembic upgrade head`.

---

## 5. Autenticação e níveis de acesso

### 5.1 Login

- Todas as telas exigem login (`/login`). A sessão é mantida por cookie assinado com a `SECRET_KEY` (persistida em `.secret_key` na raiz, ou definida por variável de ambiente).
- Senhas são armazenadas como **hash** (via `werkzeug.security`) — nunca em texto puro.
- Cada usuário pode trocar a própria senha em `/trocar-senha`.
- Todos os formulários POST são protegidos contra **CSRF** (Flask-WTF); requisições AJAX enviam o token no header `X-CSRFToken`.

### 5.2 Papéis (roles)

| Papel | O que pode fazer |
|---|---|
| **Inicial** | Todas as telas de Produção e Custos. **Não** vê nem acessa Pedidos e Movimento (os links nem aparecem no menu). O lançamento de custo em linhas de pedido, dentro da tela de custo, continua liberado. |
| **Gerente** | Acesso a todas as telas, incluindo Pedidos e Movimento. |
| **Admin** | Tudo do Gerente + administração de usuários (`/admin/usuarios`: criar, ativar/desativar, resetar senha) e gestão da chave da API (`/admin/api-key`). |

A checagem é centralizada: o `before_request` global consulta `usuario.pode_acessar_endpoint(endpoint)` a cada requisição, então não é possível burlar digitando a URL diretamente.

### 5.3 Usuários iniciais

Na primeira execução, o sistema cria:

- O usuário **admin** (senha definida pela variável de ambiente `ADMIN_PASSWORD` na primeira criação).
- Um usuário por operador do chão de fábrica (lista em `app/config.py`), com papel Inicial e **senha inicial igual ao próprio login** — cada operador deve trocá-la em `/trocar-senha` no primeiro acesso.

---

## 6. Fluxo de produção: do lançamento ao relatório

```
   Comanda/OF chega                    CSV Sisplan
         │                                  │
         ▼                                  ▼
 [Tela de Lançamento] ──grava/atualiza──▶ producao      [Pedidos] ──importa──▶ pedidos
         │  (upsert por Nº OF)               │                                   │
         │  calcula métricas                 │                                   │
         ▼                                   ▼                                   ▼
   Histórico / OF-Refugo /            [/custo Relatório]                   [Movimento]
   Comparação Quantidade /            cruza produção com               atribui custo das OFs
   Comparativo Mensal / Análise       custo_papel + custo_operacional  aos pedidos de venda
```

Pontos-chave do fluxo:

1. **Upsert por OF**: ao clicar em "Lançar", se já existe um registro com aquele `num_of`, ele é **atualizado**; senão, é **inserido**. Isso permite lançar a OF em etapas (ex.: primeiro a parte da Impressora, dias depois a SOS e a Inspeção) sem criar duplicatas. A tela também tem "Buscar OF" para carregar um lançamento existente no formulário, e "Duplicar" para iniciar uma OF nova a partir de uma parecida.
2. **Métricas calculadas na gravação**: refugo %, eficiência, velocidade, consumos e perdas são calculados no backend (`app/business.py` + `app/services/producao_service.py`) e gravados como colunas — as telas de consulta apenas exibem.
3. **Número do Pedido** é o elo entre produção e comercial: é ele que permite ao relatório de custo e à tela Movimento ligar OFs a pedidos do Sisplan.

---

## 7. Telas do sistema, uma a uma

### 7.1 Lançamento (`/`)

Tela inicial. Formulário dividido em grupos que espelham as etapas físicas:

- **Identificação**: Nº OF, Data(s), Serviço, Nº do Pedido, Papel, Formato, Tipo (SACOLA/CARTUCHO), Tipo de Impressão (SOS ou Pré-impresso), Peso Milheiro, Qtd. Clichês, Quantidade Comanda.
- **Impressora**: máquina, operador, data, quantidade, refugos (acerto flexo, flexo, pré-impresso), horários de acerto e de produção (até 4 dias).
- **SOS**: máquina (SOS 1–4), operador, data, quantidade, refugos (acerto SOS, SOS), horários de acerto e produção (até 4 dias).
- **Robô e Inspeção**: robô alça, operador, data, quantidade, Refugo Robô (peças), Refugo Inspeção Final (peças), Quantidade Inspeção Final, datas.
- **Observações**: três campos (Impressora, SOS, Robô) que são gravados unificados em um único campo no banco e re-separados na edição.

Botões: **Lançar** (grava com upsert), **Buscar OF**, **Duplicar**.

### 7.2 Histórico (`/historico`)

A visão mais completa: todas as colunas do lançamento + métricas calculadas, com:

- **Filtros avançados** (modal): serviço, OF, pedido, períodos por data de cada etapa (SOS, Impressora, Robô, Inspeção), operadores, máquinas SOS, tipo de impressão.
- **Ordenação** clicando em qualquer cabeçalho de coluna; cabeçalhos de colunas calculadas mostram a fórmula como tooltip.
- **Paginação** (100 registros por página) e **Exportar Excel** (respeita os filtros ativos).
- Colunas Nº OF e Serviço ficam **fixas à esquerda** ao rolar horizontalmente.
- Ações por linha: **Editar** (abre o formulário de lançamento preenchido) e **Excluir**.
- Cabeçalhos com cores por etapa: azul (identificação), verde (Impressora), ciano (SOS), laranja (perdas/consumo).

Filtros, ordenação e paginação atualizam **só a tabela**, sem recarregar a página (HTMX — ver seção 12).

### 7.3 OF-Refugo (`/of-refugo`)

Versão simplificada do histórico focada em refugo por OF. Colunas: OF, Serviço, Pedido, Data Inspeção Final, Qtde Comanda, Qtde Inspeção Final, Refugo Geral Peças, **Porcentagem de Refugo Pedido**, refugos por etapa e Consumo Total.

A coluna Porcentagem de Refugo Pedido é colorida por faixa:

| Faixa | Cor |
|---|---|
| ≤ 3% | verde |
| > 3% e < 5% | azul |
| ≥ 5% e < 10% | amarelo |
| ≥ 10% | vermelho |

### 7.4 Comparação Quantidade (`/comparacao-quantidade`)

Confere a consistência entre a etapa de impressão e a de formação. Só exibe OFs com quantidade em **ambas** as etapas. Colunas principais:

- **Refugo SOS Peças** = refugo SOS em kg convertido para peças pelo milheiro (arredondado para cima).
- **Diferença** = `(Quantidade SOS + Refugo SOS Peças) − Quantidade Impressora`. Uma diferença grande (positiva ou negativa) indica erro de contagem ou de lançamento; a célula é colorida por faixa (abaixo de −150 / −100, acima de 100 / 150).
- Coluna Observações opcional (botão "Mostrar Observações").

### 7.5 Comparativo Mensal (`/comparativo-mensal`)

Consolidação mensal do ano: quantidade produzida, metas (editáveis por mês na própria tela, gravadas em `metas_mensais`), percentuais médios de refugo, consumos. Inclui **gráfico interativo** (Chart.js) com barras de quantidade produzida e linhas de % de refugo em eixo secundário. Exporta para Excel.

### 7.6 Análise (`/analise`)

Visões agregadas de desempenho (por operador/máquina/período), montadas com pandas sobre a tabela `producao`.

### 7.7 Pedidos (`/pedidos`) — Gerente/Admin

Pedidos de venda do Sisplan:

- **Atualizar Banco de Dados** lê o arquivo `sisplanpedidos.csv` da raiz do projeto e importa as linhas novas. A importação:
  - Ignora linhas inválidas e o grupo `CLICHES`;
  - **Deduplica**: linha já existente no banco não é importada de novo;
  - Reporta o resultado (inseridos / ignorados / duplicados) em mensagem na tela.
- Filtros, ordenação, paginação e exportação Excel como no Histórico.
- Exclusão individual de registros.

### 7.8 Movimento (`/movimento`) — Gerente/Admin

Mesmos pedidos da tela anterior, acrescidos das colunas **CUSTO** e **MARGEM**. O custo é estimado automaticamente a partir das OFs produzidas — a lógica completa está na seção 10.

### 7.9 Custos (`/custo`, `/custos-papel`, `/custos-operacionais`)

Ver seção 9.

### 7.10 Administração (`/admin/usuarios`, `/admin/api-key`) — Admin

- **Usuários**: criar (login, nome, senha, papel), ativar/desativar, resetar senha. Um admin não pode desativar a própria conta.
- **API de Integrações**: visualizar, copiar e regenerar a chave `X-API-Key` usada pela API JSON (com exemplo de chamada `curl` pronto).

---

## 8. Fórmulas e cálculos detalhados

Todos os cálculos abaixo estão implementados em `app/business.py` (função `calcular_metricas_producao`) e `app/services/producao_service.py` (função `montar_campos_producao`), e são executados **no momento do lançamento/edição**. Notação: `milheiro` = peso em kg de 1.000 peças; `peso_unidade = milheiro ÷ 1000`.

### 8.1 Agrupamento dos refugos (kg)

```
Refugo SOS (kg)      = refugo_sos + refugo_acerto_sos
Refugo Flexo (kg)    = refugo_flexo + refugo_acerto_flexo + refugo_pre_impresso
Refugo Produção Total (kg) = soma dos 5 refugos acima
```

### 8.2 Percentuais de refugo

O percentual compara o refugo (kg) com o total processado (peso das peças boas + refugo):

```
Peso boas SOS (kg)   = Quantidade SOS × peso_unidade
Refugo % SOS         = Refugo SOS ÷ (Peso boas SOS + Refugo SOS) × 100

Peso boas Flexo (kg) = Quantidade Impressora × peso_unidade
Refugo % Impressora  = Refugo Flexo ÷ (Peso boas Flexo + Refugo Flexo) × 100
```

### 8.3 Conversões peças ↔ kg

```
Refugo Produção (peças) = (Refugo SOS kg + Refugo Flexo kg) × 1000 ÷ milheiro
Refugo Robô (kg)          = Refugo Robô (peças) × peso_unidade
Refugo Inspeção Final (kg) = Refugo Inspeção Final (peças) × peso_unidade
```

### 8.4 Perdas gerais e consumo

```
Refugo Geral (kg)  ("perdas_geral_kg") =
    peso_unidade × (Refugo Robô peças + Refugo Inspeção peças) + Refugo Produção Total (kg)

Refugo Geral (peças) ("perdas_geral") =
    Refugo Produção (peças) + Refugo Robô (peças) + Refugo Inspeção Final (peças)

Consumo Útil (kg)  = (Quantidade Inspeção Final ÷ 1000) × milheiro
Consumo Total (kg) = Consumo Útil + Refugo Geral (kg)
```

Interpretação: o Consumo Total é todo o papel que entrou na OF; o Consumo Útil é a parte que virou produto aprovado.

### 8.5 Tempos

Horários são digitados como `HH:MM`. Cada segmento suporta **virada de dia** (se o fim é menor que o início, soma-se 24 h):

```
Tempo de segmento = fim − início            (ou fim − início + 24h)
Tempo Produção SOS        = soma dos segmentos dos dias 1 a 4 (SOS)
Tempo Produção Impressora = soma dos segmentos dos dias 1 a 4 (Impressora)
Tempo Acerto SOS          = Fim Acerto − Início Acerto (SOS)
Tempo Acerto Impressora   = Fim Acerto − Início Acerto (Impressora)
```

### 8.6 Velocidades

```
Velocidade SOS (un/min)        = Quantidade SOS ÷ (Tempo Produção SOS em minutos)
Velocidade Impressora (un/min) = Quantidade Impressora ÷ (Tempo Produção Impressora em minutos)
```

### 8.7 Eficiência (índice composto)

A eficiência compara o realizado com padrões **ideais** cadastrados em `app/config.py`:

- `IDEAL_SPEED_RATES`: velocidade ideal (un/h) **por formato** (ex.: `18X30X10` → 4.100 un/h);
- `IDEAL_SETUP_TIMES_MIN`: tempo ideal de acerto **por quantidade de clichês** (1 → 15 min, 2 → 22,5 min, 3 → 32,5 min);
- `IDEAL_SCRAP_RATES_SOS_PCT`: refugo ideal (%) **por tipo de papel** (ex.: `BAG 80GRS` → 6%).

```
performance_velocidade = velocidade real ÷ velocidade ideal
performance_acerto     = tempo ideal de acerto ÷ tempo real de acerto
performance_refugo     = (100 − refugo % real) ÷ (100 − refugo % ideal)

Eficiência (%) = performance_velocidade × performance_acerto × performance_refugo × 100
```

Ou seja: produzir na velocidade ideal, com acerto no tempo ideal e refugo no nível ideal resulta em 100%. Cada desvio multiplica (penaliza) o índice.

### 8.8 Observações unificadas

Os três campos de observação (Impressora, SOS, Robô) são gravados em uma única coluna com o formato `Impressora: '...'   |   SOS: '...'   |   Robô: '...'` e re-separados automaticamente ao editar. Aspas simples são escapadas para não quebrar o formato.

---

## 9. Módulo de Custos

### 9.1 Cadastros

- **Custo Papel** (`/custos-papel`): custo por kg de cada tipo de papel (ex.: BRANCO 110G, BAG 80GRS...). Editável a qualquer momento; o relatório sempre usa o valor vigente.
- **Custos Operacionais** (`/custos-operacionais`): despesas unitárias **por peça produzida** (ex.: ALÇA, TINTA, mão de obra, energia). O total dessas despesas compõe o custo operacional unitário.

### 9.2 Relatório de custo (`/custo`)

Para cada OF lançada (filtrável por período, serviço e OF), o sistema calcula:

```
Custo Papel (R$)        = Consumo Total (kg) × custo do kg do papel da OF

Custo Operacional unitário depende do TIPO da OF:
  SACOLA   → todas as despesas operacionais (incluindo ALÇA)
  CARTUCHO → apenas a despesa TINTA
  outros   → todas as despesas exceto ALÇA

Custos Adicionais (R$)  = Quantidade × custo operacional unitário
Custo Final (R$)        = Custo Papel + Custos Adicionais
```

A tela também exibe o painel "Resultado do Cálculo" com Consumo Útil (kg), Refugo Total (kg) e **Soma Consumo (kg)** (= Consumo Útil + Refugo Total). Exporta CSV em formato PT-BR (ponto e vírgula como separador, vírgula decimal).

---

## 10. Movimento: cálculo de custo por pedido

A tela Movimento responde à pergunta: *"quanto custou produzir cada pedido de venda?"*. Como um pedido do Sisplan nem sempre tem uma OF diretamente ligada a ele, o sistema usa a seguinte estratégia (implementada em `app/movimento.py`):

1. **Índice de custos por OF**: a partir do relatório de custo (seção 9), monta-se um índice `(nº do pedido, medida) → {quantidade, custo final, coeficiente}`, onde `coeficiente = custo final ÷ quantidade` (custo por peça daquela OF).

2. **Correspondência direta**: se o pedido da linha tem uma OF com o mesmo número de pedido e a mesma medida, usa-se o coeficiente dela.

3. **Correspondência por vizinhança**: se não há OF direta, o sistema procura pedidos **"vizinhos"** — mesmos *grupo* (normalizado para SACOLA/CARTUCHO), *medida* e *cliente (fantasia)*, com número de pedido a até **±10** de distância — e usa o coeficiente da OF do vizinho mais próximo. Isso cobre o caso comum de um lote produzido em uma OF atender vários pedidos sequenciais do mesmo cliente.

4. **Distribuição com tolerância**: os pedidos vizinhos são acumulados em ordem crescente até a soma das quantidades atingir a quantidade da OF (com tolerância de **20%**). Só os pedidos dentro desse acúmulo recebem custo — evita atribuir o custo de uma OF a mais pedidos do que ela realmente produziu.

5. **Custo da linha** = `coeficiente × quantidade do pedido`. Linhas sem correspondência ficam com custo vazio. Um custo lançado **manualmente** na linha (pela tela de custo) tem prioridade sobre o calculado.

---

## 11. API JSON para integrações

API **somente leitura** em `/api/v1/`, para BI, automações ou outros sistemas — nenhuma rota altera dados.

- **Autenticação**: header `X-API-Key: <chave>` (gerada/consultada por um admin em `/admin/api-key`, persistida em `.api_key` ou fixada pela variável de ambiente `API_KEY`), **ou** a sessão de login normal (útil para testar no navegador).
- **Paginação**: `?page=` e `?per_page=` (máx. 500); resposta no envelope `{"data": [...], "page", "per_page", "total", "total_paginas"}`.
- **Índice autoexplicativo**: `GET /api/v1/` lista todas as rotas e filtros.

| Rota | Conteúdo |
|---|---|
| `GET /api/v1/producao` | Lançamentos (filtros: `num_of`, `servico`, `operador`, `data`) |
| `GET /api/v1/producao/<id>` | Um lançamento |
| `GET /api/v1/pedidos` | Pedidos Sisplan (filtros: `pedido`, `fantasia`, `cidade`, `uf`, `grupo`) |
| `GET /api/v1/movimento` | Pedidos com custo calculado |
| `GET /api/v1/custos/papel` | Custos por kg de papel |
| `GET /api/v1/custos/operacionais` | Despesas operacionais |
| `GET /api/v1/resumo-mensal?ano=AAAA` | Totais de produção e refugo por mês |

Exemplo:

```bash
curl -H "X-API-Key: <chave>" "http://SERVIDOR:8082/api/v1/producao?per_page=10"
```

---

## 12. Frontend: HTMX e Chart.js

### 12.1 HTMX (navegação sem reload)

Nas cinco telas de listagem (Histórico, Pedidos, Movimento, OF-Refugo, Comparação de Quantidade), filtrar, ordenar e paginar troca **apenas a tabela**, não a página inteira:

- Os links/formulários dessas ações têm `hx-get` + `hx-target="#<tela>-resultado"` + `hx-push-url="true"`. O HTMX faz a requisição via `fetch` (enviando `HX-Request: true`) e substitui só o conteúdo do contêiner de resultado, mantendo a URL do navegador atualizada (botão Voltar e F5 funcionam normalmente).
- No servidor, a mesma rota detecta o header e devolve só o fragmento (`templates/partials/*_resultado.html`) — o mesmo fragmento que a página completa inclui via `{% include %}`, então os dois caminhos nunca divergem.
- O reposicionamento das colunas fixas é reexecutado após cada troca (evento `htmx:afterSwap`).
- Exportar Excel e "Atualizar Banco de Dados" permanecem como navegação normal (download / redirect com mensagem).

### 12.2 Chart.js (gráfico do Comparativo Mensal)

O gráfico é desenhado **no navegador**: o backend envia os dados em JSON embutido na página e `static/js/comparativo_mensal_chart.js` monta o gráfico (barras de quantidade + linhas de % de refugo em eixo duplo). Substituiu a antiga geração de imagem PNG no servidor com matplotlib — eliminando esse custo de CPU/RAM por requisição e tornando o gráfico interativo (tooltips, legenda clicável).

---

## 13. Logs e diagnóstico

| Arquivo | Conteúdo |
|---|---|
| `logs/app.log` | Mensagens da aplicação: inicialização, avisos, **exceções não tratadas com stack trace completo**, resultado dos backups automáticos. |
| `logs/access.log` | Uma linha por requisição HTTP: `metodo=GET rota=/historico status=200 duracao_ms=12.3 usuario=admin ip=192.168.0.10`. |
| `logs/service_stdout.log` / `service_stderr.log` | Saída bruta do processo quando roda como serviço Windows (capturada pelo NSSM) — útil para erros de inicialização. |

- Rotação automática: 5 MB por arquivo, últimos 5 mantidos (configurado em `app/logging_config.py`, stdlib pura).
- Nível configurável por `LOG_LEVEL` (padrão `INFO`; use `DEBUG` para investigar).
- Diagnóstico rápido quando rodando como serviço: `deploy\status_servico.ps1` mostra o status do serviço + últimas linhas de todos os logs.

---

## 14. Como rodar o sistema

### 14.1 Pré-requisitos

- Windows 10/11 com **Python 3.12+** (o `iniciar_servidor.bat` tenta instalar via winget se faltar).
- Porta **8082** liberada no Firewall do Windows para acesso de outras máquinas da rede.

### 14.2 Modo desenvolvimento (para programar/testar)

```powershell
cd "d:\dev npd\PRODUCAO\NPD"
python -m venv venv                      # só na primeira vez
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\python.exe app.py
```

Sobe o servidor de desenvolvimento do Flask em `http://localhost:8082` com **auto-reload** (recarrega ao salvar arquivos) e debugger.

> **Atenção**: o modo debug nunca deve ficar ligado em produção — o debugger do Werkzeug permite execução remota de código. Em produção use sempre uma das opções abaixo.

### 14.3 Modo produção manual (janela aberta)

Opção simples: dar dois cliques em **`iniciar_servidor.bat`**. O script cria o venv se necessário, instala dependências, mostra os endereços de acesso e inicia o **Waitress** (servidor de produção) via `wsgi.py`. A janela precisa ficar aberta; `CTRL+C` para o servidor.

Equivalente manual:

```powershell
.\venv\Scripts\python.exe wsgi.py
```

### 14.4 Modo produção recomendado: serviço do Windows (NSSM)

Instala o sistema como serviço — roda em segundo plano, inicia com o Windows e reinicia sozinho se cair:

1. Baixe o NSSM em <https://nssm.cc/download> e copie `nssm.exe` para a pasta `deploy\` do projeto.
2. Garanta que o venv existe (rode o `iniciar_servidor.bat` uma vez, se preciso).
3. Em um **PowerShell como Administrador**:

```powershell
cd "d:\dev npd\PRODUCAO\NPD\deploy"
.\instalar_servico.ps1        # cria e inicia o serviço "NPD-Producao"
.\status_servico.ps1          # confere status + últimas linhas dos logs
.\desinstalar_servico.ps1     # remove o serviço (se precisar)
```

Gerenciamento pelo próprio Windows: `Start-Service NPD-Producao`, `Stop-Service NPD-Producao`, `Restart-Service NPD-Producao`, ou `services.msc`.

### 14.5 Primeiro acesso

1. Abra `http://localhost:8082` (ou `http://IP_DO_SERVIDOR:8082` de outra máquina).
2. Entre com o usuário **admin** (senha definida via `ADMIN_PASSWORD` na primeira execução).
3. Em `/admin/usuarios`, crie os usuários das demais pessoas com o papel adequado.
4. Cadastre os custos em `/custos-papel` e `/custos-operacionais` para o relatório de custo funcionar.
5. Coloque o `sisplanpedidos.csv` na raiz e clique em "Atualizar Banco de Dados" na tela Pedidos.

---

## 15. Testes automatizados

Suíte em `tests/` (pytest), com banco **temporário isolado** por execução — os testes nunca tocam o banco real:

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -v
```

| Arquivo | Cobre |
|---|---|
| `tests/conftest.py` | Infra: banco temporário, usuários de teste, clientes autenticados por papel (admin/gerente/inicial/anônimo). |
| `tests/test_routes_smoke.py` | Login/logout, redirecionamentos, permissões por papel, ciclo lançar → editar → excluir, upsert por OF. |
| `tests/test_api.py` | Autenticação da API (chave válida/inválida/sessão), paginação, endpoints, página de administração da chave. |
| `tests/test_htmx.py` | Página completa vs. fragmento HTMX nas 5 telas de listagem, filtros no fragmento. |

Regra de ouro: **rodar a suíte antes e depois de qualquer alteração de código**. Ela é a rede de segurança do projeto (o projeto não usa Git nesta máquina).

---

## 16. Manutenção: backups e migrações de banco

### 16.1 Backups automáticos

- Ao iniciar o servidor e a cada **24 h**, uma cópia consistente do banco é gravada em `backup/dados_producao_AAAAMMDD_HHMMSS.db` (usa a API de backup do SQLite — segura mesmo com o banco em uso).
- Retenção: **30 dias** (cópias mais antigas são apagadas automaticamente).
- **Restaurar**: pare o servidor, substitua `dados_producao.db` pela cópia desejada, inicie o servidor.

> Recomenda-se copiar periodicamente a pasta `backup/` para outra máquina ou drive — backups no mesmo disco não protegem contra falha do disco.

### 16.2 Migrações (Alembic)

```powershell
# criar migração nova (depois editar o arquivo gerado em migrations/versions/)
.\venv\Scripts\python.exe -m alembic revision -m "descricao da mudanca"

# aplicar migrações pendentes
.\venv\Scripts\python.exe -m alembic upgrade head

# ver revisão atual do banco
.\venv\Scripts\python.exe -m alembic current
```

---

## 17. Solução de problemas (troubleshooting)

| Sintoma | Causa provável | Solução |
|---|---|---|
| Página não abre de outro PC | Firewall bloqueando a porta 8082 | Criar regra de entrada TCP 8082 no Firewall do Windows do servidor |
| "database is locked" persistente | Processo antigo preso segurando o banco | Verificar processos Python duplicados (`netstat -ano | findstr 8082`) e finalizar os extras |
| `ImportError: DLL load failed ... Controle de Aplicativo bloqueou` | Windows Smart App Control bloqueando DLLs de versão recente do pandas | Manter `pandas>=1.3.0,<3` (já fixado no `requirements.txt`); recriar o venv se necessário |
| Login do admin não funciona | Senha alterada/perdida | Outro admin reseta em `/admin/usuarios`; sem outro admin, redefinir via script Python no servidor |
| Serviço não inicia | venv ausente, porta ocupada ou erro de inicialização | Ver `logs\service_stderr.log` e `logs\app.log`; rodar `wsgi.py` manualmente para ver o erro no console |
| Tabela não atualiza ao filtrar | JavaScript desabilitado ou htmx não carregou | Ver console do navegador (F12); os links continuam funcionando como navegação normal mesmo sem htmx |
| Custo vazio no Movimento | OF sem Nº do Pedido, sem OF vizinha (±10) compatível, ou custos de papel/operacionais não cadastrados | Conferir o Nº do Pedido na OF e os cadastros de custo |
| Excel não exporta | Erro nos dados do período filtrado | Ver mensagem na tela e `logs/app.log` |

---

## Apêndice A — Variáveis de ambiente

| Variável | Padrão | Função |
|---|---|---|
| `SECRET_KEY` | gerada e persistida em `.secret_key` | Assinatura das sessões (fixar em produção com múltiplas instâncias) |
| `ADMIN_PASSWORD` | — | Senha do usuário admin **na primeira criação** do banco de usuários |
| `API_KEY` | gerada e persistida em `.api_key` | Fixa a chave da API JSON (recomendado em produção) |
| `DB_NAME` | `dados_producao.db` na raiz | Caminho do banco (usada pelos testes para isolar o banco) |
| `LOG_DIR` | `logs/` (junto do banco) | Pasta dos arquivos de log |
| `LOG_LEVEL` | `INFO` | Nível de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `FLASK_DEBUG` | `true` no `app.py` | `false` desativa o modo debug (obrigatório em produção) |
| `USE_WAITRESS` / `FLASK_ENV=production` | — | Faz o `app.py` usar Waitress em vez do servidor de desenvolvimento |

## Apêndice B — Arquivos gerados em tempo de execução

Todos ficam fora do versionamento (`.gitignore`):

| Arquivo/Pasta | Conteúdo |
|---|---|
| `dados_producao.db` (+ `-wal`, `-shm`) | Banco SQLite e arquivos do modo WAL |
| `.secret_key` | Chave de sessão gerada automaticamente |
| `.api_key` | Chave da API JSON gerada automaticamente |
| `backup/` | Backups diários do banco (30 dias) |
| `logs/` | `app.log`, `access.log`, logs do serviço NSSM |
| `venv/` | Ambiente virtual Python |

---

*Documento gerado a partir do código-fonte do sistema. Em caso de divergência entre este manual e o comportamento do sistema, o código-fonte prevalece; reporte a divergência para atualização do manual.*
