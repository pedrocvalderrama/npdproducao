@echo off
title PRODUÇÃO - Servidor de Producao
color 0A

REM Garante que estamos na pasta do script (NPD)
cd /d "%~dp0"

echo ========================================
echo   PRODUÇÃO - Servidor de Producao
echo ========================================
echo.

REM Tenta encontrar Python (python ou py -3)
set PYTHON_CMD=
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto :python_ok
)
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3
    goto :python_ok
)

REM Python nao encontrado - tenta instalar via winget (Windows 10/11)
echo Python nao encontrado. Tentando instalar automaticamente...
echo.
where winget >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRO: winget nao disponivel. Instale o Python manualmente:
    echo   1. Acesse https://www.python.org/downloads/
    echo   2. Baixe e instale o Python 3.12 ou superior
    echo   3. Marque "Add Python to PATH" na instalacao
    echo   4. Execute este arquivo novamente.
    pause
    exit /b 1
)

echo Instalando Python via winget...
winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if %errorlevel% neq 0 (
    echo.
    echo Falha na instalacao. Tente instalar o Python manualmente em https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo Python foi instalado. FECHE esta janela, abra uma NOVA janela do Prompt de Comando,
echo va ate a pasta do projeto e execute iniciar_servidor.bat novamente.
pause
exit /b 0

:python_ok
echo Python encontrado.
%PYTHON_CMD% --version
echo.

REM Cria ambiente virtual se nao existir
if not exist "venv\Scripts\activate.bat" (
    echo Criando ambiente virtual...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo ERRO ao criar ambiente virtual.
        pause
        exit /b 1
    )
    echo.
)

REM Ativa o ambiente virtual
echo Ativando ambiente virtual...
call venv\Scripts\activate.bat
echo.

REM Instala/atualiza dependencias
echo Instalando ou atualizando dependencias (requirements.txt)...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo AVISO: Algum pacote pode ter falhado. Tentando iniciar mesmo assim...
)
echo.

echo Iniciando servidor Waitress na porta 8082...
echo.
setlocal EnableDelayedExpansion
set LOCAL_IP=
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch '^127\.' } | Select-Object -First 1 -ExpandProperty IPAddress" 2^>nul`) do set LOCAL_IP=%%i
echo Acesse NESTA maquina:  http://localhost:8082
if defined LOCAL_IP (echo Acesse de OUTROS PCs:  http://!LOCAL_IP!:8082) else (echo Para outros PCs: execute "ipconfig" e use http://[IP]:8082)
echo.
echo Se outros PCs nao conseguirem acessar, libere a porta 8082 no Firewall do Windows.
echo   Configuracoes ^> Firewall ^> Regras de entrada ^> Nova regra ^> Porta ^> TCP 8082 ^> Permitir
echo.
echo Pressione CTRL+C para parar o servidor
echo.

REM Inicia o servidor usando wsgi.py
python wsgi.py

REM Se o servidor parar, mantem a janela aberta
if errorlevel 1 (
    echo.
    echo ERRO ao iniciar o servidor!
    pause
)
