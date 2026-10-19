<#
.SYNOPSIS
    Mostra o status do serviço do NPD e as últimas linhas dos logs
    (aplicação e do próprio NSSM), útil para diagnóstico rápido.

.PARAMETER ServiceName
    Nome do serviço. Padrão: "NPD-Producao".

.PARAMETER Linhas
    Quantidade de linhas finais de cada arquivo de log a exibir. Padrão: 20.

.EXAMPLE
    .\status_servico.ps1
#>
param(
    [string]$ServiceName = "NPD-Producao",
    [int]$Linhas = 20
)

$ProjetoDir = Split-Path -Parent $PSScriptRoot
$LogsDir = Join-Path $ProjetoDir "logs"

Write-Host "=== Status do servico '$ServiceName' ===" -ForegroundColor Cyan
$servico = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($servico) {
    $servico | Format-Table -AutoSize
} else {
    Write-Host "Servico nao encontrado (nao instalado?)." -ForegroundColor Yellow
}

foreach ($arquivo in @("app.log", "access.log", "service_stdout.log", "service_stderr.log")) {
    $caminho = Join-Path $LogsDir $arquivo
    Write-Host ""
    Write-Host "=== Ultimas $Linhas linhas de $arquivo ===" -ForegroundColor Cyan
    if (Test-Path $caminho) {
        Get-Content $caminho -Tail $Linhas
    } else {
        Write-Host "(arquivo ainda nao existe)" -ForegroundColor DarkGray
    }
}
