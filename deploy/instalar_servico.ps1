<#
.SYNOPSIS
    Instala o NPD como serviço do Windows usando o NSSM, para rodar em segundo
    plano (sem janela de console aberta) e reiniciar automaticamente no boot
    do servidor e em caso de falha (Fase 4 da auditoria de otimização).

.DESCRIPTION
    Cria um serviço do Windows que executa `venv\Scripts\python.exe wsgi.py`
    (Waitress) a partir da raiz do projeto. Precisa ser executado como
    Administrador. Requer o NSSM (https://nssm.cc/download) — baixe o
    executável correspondente à arquitetura do servidor (normalmente win64)
    e coloque `nssm.exe` dentro desta pasta `deploy\`, ou em qualquer local
    já presente no PATH do sistema.

.PARAMETER ServiceName
    Nome do serviço do Windows a ser criado. Padrão: "NPD-Producao".

.PARAMETER SecretKey
    Valor opcional para a variável de ambiente SECRET_KEY do serviço (chave
    de sessão fixa). Se omitido, o app gera/reaproveita `.secret_key` na raiz
    do projeto automaticamente — normalmente não é necessário informar.

.EXAMPLE
    # Executar em um PowerShell como Administrador, a partir da pasta deploy\:
    .\instalar_servico.ps1

.EXAMPLE
    .\instalar_servico.ps1 -ServiceName "NPD-Producao-Teste"
#>
param(
    [string]$ServiceName = "NPD-Producao",
    [string]$SecretKey = ""
)

$ErrorActionPreference = "Stop"

# Raiz do projeto = pasta pai de deploy\ (onde este script está)
$ProjetoDir = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjetoDir "venv\Scripts\python.exe"
$WsgiScript = Join-Path $ProjetoDir "wsgi.py"
$LogsDir = Join-Path $ProjetoDir "logs"

# Localiza o nssm.exe: primeiro dentro de deploy\, senão tenta o PATH
$NssmLocal = Join-Path $PSScriptRoot "nssm.exe"
if (Test-Path $NssmLocal) {
    $Nssm = $NssmLocal
} else {
    $Nssm = (Get-Command "nssm.exe" -ErrorAction SilentlyContinue).Source
}
if (-not $Nssm) {
    Write-Host "ERRO: nssm.exe nao encontrado." -ForegroundColor Red
    Write-Host "Baixe em https://nssm.cc/download e coloque o nssm.exe dentro de:"
    Write-Host "  $PSScriptRoot"
    Write-Host "(ou em qualquer pasta que ja esteja no PATH do Windows)."
    exit 1
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "ERRO: ambiente virtual nao encontrado em $PythonExe" -ForegroundColor Red
    Write-Host "Rode 'iniciar_servidor.bat' uma vez (ou crie o venv manualmente) antes de instalar o servico."
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

Write-Host "Instalando o servico '$ServiceName'..." -ForegroundColor Cyan
Write-Host "  Python:    $PythonExe"
Write-Host "  Script:    $WsgiScript"
Write-Host "  Pasta:     $ProjetoDir"
Write-Host "  Logs NSSM: $LogsDir\service_stdout.log / service_stderr.log"
Write-Host ""

# Remove um servico antigo com o mesmo nome, se existir (permite reinstalar)
$servicoExistente = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($servicoExistente) {
    Write-Host "Servico ja existe, removendo antes de reinstalar..." -ForegroundColor Yellow
    & $Nssm stop $ServiceName confirm | Out-Null
    & $Nssm remove $ServiceName confirm | Out-Null
    Start-Sleep -Seconds 2
}

& $Nssm install $ServiceName $PythonExe $WsgiScript
& $Nssm set $ServiceName AppDirectory $ProjetoDir
& $Nssm set $ServiceName DisplayName "NPD - Sistema de Producao e Custos"
& $Nssm set $ServiceName Description "Servidor Flask/Waitress do sistema NPD (producao e custos). Instalado via NSSM (Fase 4 da auditoria de otimizacao)."
& $Nssm set $ServiceName Start SERVICE_AUTO_START

# Reinicia o servico automaticamente se ele cair (ex.: excecao nao tratada
# que derrube o processo), com um pequeno intervalo para nao entrar em loop
# de reinicio imediato caso o erro seja persistente.
& $Nssm set $ServiceName AppExit Default Restart
& $Nssm set $ServiceName AppRestartDelay 5000
& $Nssm set $ServiceName AppThrottle 3000

# stdout/stderr do processo (diferente do app.log/access.log gerados pelo
# proprio Flask em app/logging_config.py) — util para capturar erros de
# inicializacao que aconteçam antes do logging da aplicacao estar de pe.
# O NSSM roda a propria rotacao para nao crescer sem limite.
& $Nssm set $ServiceName AppStdout (Join-Path $LogsDir "service_stdout.log")
& $Nssm set $ServiceName AppStderr (Join-Path $LogsDir "service_stderr.log")
& $Nssm set $ServiceName AppRotateFiles 1
& $Nssm set $ServiceName AppRotateOnline 1
& $Nssm set $ServiceName AppRotateBytes 5242880

# Variaveis de ambiente do processo do servico. FLASK_DEBUG=false desativa
# o modo debug (obrigatorio em produção: o debugger do Werkzeug permite
# execução remota de código se ligado por engano).
$envVars = "FLASK_DEBUG=false`nUSE_WAITRESS=true"
if ($SecretKey) {
    $envVars += "`nSECRET_KEY=$SecretKey"
}
& $Nssm set $ServiceName AppEnvironmentExtra $envVars

Write-Host ""
Write-Host "Iniciando o servico..." -ForegroundColor Cyan
& $Nssm start $ServiceName

Start-Sleep -Seconds 2
Get-Service -Name $ServiceName | Format-Table -AutoSize

Write-Host ""
Write-Host "Servico '$ServiceName' instalado. Acesse http://localhost:8082 (ou o IP do servidor)." -ForegroundColor Green
Write-Host "Logs da aplicacao: $ProjetoDir\logs\app.log e $ProjetoDir\logs\access.log"
Write-Host "Para desinstalar: .\desinstalar_servico.ps1"
