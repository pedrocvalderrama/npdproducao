<#
.SYNOPSIS
    Para e remove o serviço do Windows do NPD instalado via
    `instalar_servico.ps1` (Fase 4 da auditoria de otimização).

.PARAMETER ServiceName
    Nome do serviço a remover. Padrão: "NPD-Producao" (mesmo padrão usado
    por `instalar_servico.ps1`).

.EXAMPLE
    # Em um PowerShell como Administrador:
    .\desinstalar_servico.ps1
#>
param(
    [string]$ServiceName = "NPD-Producao"
)

$ErrorActionPreference = "Stop"

$NssmLocal = Join-Path $PSScriptRoot "nssm.exe"
if (Test-Path $NssmLocal) {
    $Nssm = $NssmLocal
} else {
    $Nssm = (Get-Command "nssm.exe" -ErrorAction SilentlyContinue).Source
}
if (-not $Nssm) {
    Write-Host "ERRO: nssm.exe nao encontrado (coloque em deploy\ ou no PATH)." -ForegroundColor Red
    exit 1
}

$servico = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $servico) {
    Write-Host "Servico '$ServiceName' nao esta instalado. Nada a fazer." -ForegroundColor Yellow
    exit 0
}

Write-Host "Parando o servico '$ServiceName'..." -ForegroundColor Cyan
& $Nssm stop $ServiceName confirm | Out-Null
Start-Sleep -Seconds 2

Write-Host "Removendo o servico '$ServiceName'..." -ForegroundColor Cyan
& $Nssm remove $ServiceName confirm | Out-Null

Write-Host "Servico '$ServiceName' removido." -ForegroundColor Green
