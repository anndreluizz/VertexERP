@echo off
title VertexERP

cd /d "%~dp0backend"
start "VertexERP-Backend" /min .venv\Scripts\python.exe -m uvicorn main:app

powershell -NoProfile -Command "for ($i=0; $i -lt 60; $i++) { try { Invoke-WebRequest -Uri http://127.0.0.1:8000/docs -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } }; exit 1"

cd /d "%~dp0frontend"
.venv\Scripts\python.exe app.py

taskkill /FI "WINDOWTITLE eq VertexERP-Backend*" /T /F >nul 2>&1
