# Configurações globais e constantes do sistema
import os

# Tipos de papel disponíveis no lançamento (e cadastro de custo papel)
PAPEIS = [
    'BRANCO 110G', 'BRANCO 90GRS', 'BRANCO 80GRS',
    'BAG 100GRS', 'BAG 80GRS', 'BAG 70GRS',
    'COLLEY 100G', 'ECO 70GRS', 'MONOL 70GR',
    'MG 25GRS', 'RU 32GRS', 'KRAFT 35GRS',
]

# Tipos de produto no lançamento
TIPOS = ['SACOLA', 'CARTUCHO', 'SEDA']

# Formatos (lista, velocidade ideal e largura de bobina) vivem no banco:
# tabelas formatos_cadastro / formato_tolerancias (tela Configurações de formatos).

# Tempo ideal de acerto por quantidade de clichês
IDEAL_SETUP_TIMES_MIN = {1: 15.0, 2: 22.5, 3: 32.5}
# Refugo ideal por tipo de papel
IDEAL_SCRAP_RATES_SOS_PCT = {
    'BRANCO 110G': 8.0, 'BRANCO 90GRS': 6.0, 'BRANCO 80GRS': 6.0,
    'BAG 100GRS': 6.0, 'BAG 80GRS': 6.0,
    'BAG 70GRS': 8.0, 'COLLEY 100G': 8.0, 'ECO 70GRS': 10.0,
    'MONOL 70GRS': 10.0, 'MONOL 70GR': 10.0,
    'MG 25GRS': 10.0, 'RU 32GRS': 10.0, 'KRAFT 35GRS': 10.0,
}

# Lista de operadores por categoria
OPERADORES_SOS = sorted(['JOSÉ','VALDO','JOÃO', 'PAULO', 'WELLINGTON', 'JULIO', 'LUCAS', 'WILLIAM', 'BETO', 'GABRIEL', 'ICARO'])
OPERADORES_IMPRESSORA = sorted(['ILSON', 'BETO'])
OPERADORES_ROBO = sorted(['VALDO', 'PEDRO', 'ANDREY'])

# Lista unificada de todos os operadores (para compatibilidade)
ALL_OPERADORES = sorted(OPERADORES_SOS + OPERADORES_IMPRESSORA + OPERADORES_ROBO)
# Máquinas SOS (usadas em lançamento, filtros e análises)
MAQUINAS_SOS = sorted(['SOS 1', 'SOS 2', 'SOS 3', 'SOS 4', 'RESMADEIRA' ])
# Lista de máquinas disponíveis
ALL_MAQUINAS = sorted(['IMPRESSORA'] + MAQUINAS_SOS + ['APLA-2R', 'TROCA MAQ1', 'TROCA MAQ2', 'TROCA MAQ3'])

# Caminho do banco de dados (do diretório local por padrão; sobrescrevível via
# variável de ambiente DB_NAME, usada pela suite de testes para isolar o banco
# real de produção de um banco temporário).
DB_NAME = os.environ.get('DB_NAME') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dados_producao.db')

# Porta do servidor (8082; 8080/8081 ja em uso no servidor; 5000 nao funciona)
SERVER_PORT = 8082

# Pasta dos arquivos de log (mesmo diretório do banco por padrão, para ficar
# isolada junto com o banco de teste quando DB_NAME é sobrescrito via
# variável de ambiente; sobrescrevível também via LOG_DIR).
LOG_DIR = os.environ.get('LOG_DIR') or os.path.join(os.path.dirname(DB_NAME), 'logs')
# Nível de log (DEBUG, INFO, WARNING, ERROR); INFO por padrão.
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()