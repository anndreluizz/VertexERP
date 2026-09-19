<#
.SYNOPSIS
    Gera os pacotes de ATUALIZACAO do Vertex ERP (so backend + frontend,
    sem banco/launcher) e ja envia pro PC-Servidor via Tailscale.

.DESCRIPTION
    Builda VertexERP-Backend.spec e VertexERP-Frontend.spec, zipa cada um
    em dist_final\ (mesmo nome que ja era usado manualmente:
    atualizacao_servidor.zip / atualizacao_frontend.zip) e, se -PeerTailscale
    for informado, envia os dois direto pro PC-Servidor via Taildrop.

    Nao mexe em pgdata\ nem no .env do Servidor -- esses ficam na raiz da
    pasta Servidor, ao lado do VertexERP.exe (launcher), separados das
    subpastas VertexERP-Backend\ e VertexERP-Frontend\ que este script
    atualiza. So troque essas duas subpastas no destino, nada mais.

.PARAMETER PeerTailscale
    Nome ou IP Tailscale do PC-Servidor (ver 'tailscale status'). Se omitido,
    so gera os zips em dist_final\ sem enviar.

.EXAMPLE
    .\scripts\empacotar_atualizacao.ps1
    .\scripts\empacotar_atualizacao.ps1 -PeerTailscale pc-matriz
#>

param(
    [string]$PeerTailscale = ""
)

$ErrorActionPreference = "Stop"
$Raiz = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = "$Raiz\.venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Nao achei $Python -- confirme que o .venv da raiz do projeto existe e tem PyInstaller instalado."
}

Write-Host "=== Vertex ERP - pacote de atualizacao ===" -ForegroundColor Cyan

Write-Host "`n[1/3] Build do backend..." -ForegroundColor Yellow
Push-Location "$Raiz\backend"
& $Python -m PyInstaller "VertexERP-Backend.spec" --clean --noconfirm
Pop-Location

Write-Host "`n[2/3] Build do frontend..." -ForegroundColor Yellow
Push-Location "$Raiz\frontend"
& $Python -m PyInstaller "VertexERP-Frontend.spec" --clean --noconfirm
Pop-Location

Write-Host "`n[3/3] Zipando pacotes de atualizacao..." -ForegroundColor Yellow
$DistFinal = Join-Path $Raiz "dist_final"
New-Item -ItemType Directory -Path $DistFinal -Force | Out-Null

$ZipServidor = Join-Path $DistFinal "atualizacao_servidor.zip"
$ZipFrontend = Join-Path $DistFinal "atualizacao_frontend.zip"
Remove-Item $ZipServidor -ErrorAction SilentlyContinue
Remove-Item $ZipFrontend -ErrorAction SilentlyContinue

Compress-Archive -Path "$Raiz\backend\dist\VertexERP-Backend" -DestinationPath $ZipServidor
Compress-Archive -Path "$Raiz\frontend\dist\VertexERP-Frontend" -DestinationPath $ZipFrontend

Write-Host "`nPronto!" -ForegroundColor Green
Write-Host "  $ZipServidor"
Write-Host "  $ZipFrontend"

if ($PeerTailscale -ne "") {
    Write-Host "`nEnviando via Tailscale (Taildrop) pra '$PeerTailscale'..." -ForegroundColor Yellow
    & tailscale file cp $ZipServidor "${PeerTailscale}:"
    & tailscale file cp $ZipFrontend "${PeerTailscale}:"
    Write-Host "`nEnviado. No PC-Servidor (com o Vertex ERP FECHADO):" -ForegroundColor Green
    Write-Host "  1. tailscale file get .`t(baixa os 2 zips na pasta atual)"
    Write-Host "  2. Extraia atualizacao_servidor.zip substituindo a pasta VertexERP-Backend\ dentro de Servidor\"
    Write-Host "  3. Extraia atualizacao_frontend.zip substituindo a pasta VertexERP-Frontend\ dentro de Servidor\"
    Write-Host "  4. Reabra o Vertex ERP"
} else {
    Write-Host "`nPra enviar direto pro servidor, rode de novo com:" -ForegroundColor DarkGray
    Write-Host "  .\scripts\empacotar_atualizacao.ps1 -PeerTailscale <nome-do-pc-servidor>" -ForegroundColor DarkGray
    Write-Host "  (o nome/IP aparece em 'tailscale status')" -ForegroundColor DarkGray
}
