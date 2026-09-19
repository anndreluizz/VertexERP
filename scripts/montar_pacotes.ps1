<#
.SYNOPSIS
    Gera os dois pacotes de instalacao do Vertex ERP: Servidor (banco +
    backend + frontend, igual a instalacao de sempre) e Terminal (so o
    frontend, aponta pro Servidor pela rede).

.DESCRIPTION
    Roda os 3 builds PyInstaller ja existentes (launcher, backend,
    frontend) e organiza automaticamente as pastas prontas pra copiar
    pra cada PC - evita montar na mao e esquecer algo (icone, ou
    incluir o backend/banco onde nao devia).
#>

$ErrorActionPreference = "Stop"

$Raiz = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = "$Raiz\.venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Nao achei $Python -- confirme que o .venv da raiz do projeto existe e tem PyInstaller instalado."
}

Write-Host "=== Vertex ERP - montagem dos pacotes ===" -ForegroundColor Cyan

# ==========================================
# 1) BUILDS PYINSTALLER
# ==========================================

Write-Host "`n[1/4] Build do launcher (Servidor)..." -ForegroundColor Yellow
Push-Location $Raiz
& $Python -m PyInstaller "VertexERP.spec" --clean --noconfirm
Pop-Location

Write-Host "`n[2/4] Build do backend..." -ForegroundColor Yellow
Push-Location "$Raiz\backend"
& $Python -m PyInstaller "VertexERP-Backend.spec" --clean --noconfirm
Pop-Location

Write-Host "`n[3/4] Build do frontend..." -ForegroundColor Yellow
Push-Location "$Raiz\frontend"
& $Python -m PyInstaller "VertexERP-Frontend.spec" --clean --noconfirm
Pop-Location

# ==========================================
# 2) MONTAGEM DOS PACOTES
# ==========================================

Write-Host "`n[4/4] Montando pastas Servidor e Terminal..." -ForegroundColor Yellow

$DistFinal = Join-Path $Raiz "dist_final"
$PastaServidor = Join-Path $DistFinal "Servidor"
$PastaTerminal = Join-Path $DistFinal "Terminal"

foreach ($pasta in @($PastaServidor, $PastaTerminal)) {
    if (Test-Path $pasta) {
        Remove-Item $pasta -Recurse -Force
    }
    New-Item -ItemType Directory -Path $pasta -Force | Out-Null
}

# --- Servidor: launcher + backend + frontend + postgres-portable ---
Copy-Item "$Raiz\dist\VertexERP.exe" $PastaServidor
Copy-Item "$Raiz\icone.ico" $PastaServidor
Copy-Item "$Raiz\backend\dist\VertexERP-Backend" (Join-Path $PastaServidor "VertexERP-Backend") -Recurse
Copy-Item "$Raiz\frontend\dist\VertexERP-Frontend" (Join-Path $PastaServidor "VertexERP-Frontend") -Recurse

if (Test-Path "$Raiz\postgres-portable") {
    Copy-Item "$Raiz\postgres-portable" (Join-Path $PastaServidor "postgres-portable") -Recurse
} else {
    Write-Host "  Aviso: postgres-portable nao encontrado na raiz do projeto - copie manualmente pra dist_final\Servidor antes de instalar." -ForegroundColor Red
}

# --- Terminal: so o frontend, nada de banco/backend ---
Copy-Item "$Raiz\icone.ico" $PastaTerminal
Copy-Item "$Raiz\frontend\dist\VertexERP-Frontend" (Join-Path $PastaTerminal "VertexERP-Frontend") -Recurse

Write-Host "`nPronto!" -ForegroundColor Green
Write-Host "  Servidor: $PastaServidor"
Write-Host "  Terminal: $PastaTerminal"
