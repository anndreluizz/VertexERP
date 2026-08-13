@echo off
REM Inicia o Vertex ERP direto do codigo-fonte (modo desenvolvimento) -
REM sobe o backend (uvicorn) numa janela separada e depois o frontend.
REM
REM Usa o Python do sistema com o site-packages do .venv do projeto via
REM PYTHONPATH, porque o .venv em si esta com o lancador quebrado (foi
REM criado apontando pra um Python 3.13 que nao esta mais instalado
REM nesta maquina).
REM
REM Precisa de um Postgres rodando em localhost:5432 (backend/.env).

setlocal

set "RAIZ=%~dp0"
set "PY=C:\Users\lopes\AppData\Local\Programs\Python\Python312\python.exe"
set "PYW=C:\Users\lopes\AppData\Local\Programs\Python\Python312\pythonw.exe"
set "PYTHONPATH=%RAIZ%.venv\Lib\site-packages"

if not exist "%PY%" (
    echo Python 3.12 nao encontrado em %PY%
    echo Ajuste o caminho no topo deste arquivo.
    pause
    exit /b 1
)

echo Subindo backend (uvicorn)...
start "Vertex ERP - Backend" /min cmd /k "cd /d "%RAIZ%backend" && "%PY%" -m uvicorn main:app --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

echo Abrindo o Vertex ERP...
cd /d "%RAIZ%frontend"
"%PY%" app.py
pause
