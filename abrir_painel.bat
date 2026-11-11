@echo off
setlocal
cd /d "%~dp0"
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" "%~dp0painel_programas.py"
    exit /b
)
python "%~dp0painel_programas.py"
if errorlevel 1 pause
