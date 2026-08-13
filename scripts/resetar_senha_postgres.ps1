<#
.SYNOPSIS
    Redefine a senha do usuario "postgres" no PostgreSQL 17 local (porta
    5432) pra bater com o que ja esta em backend/.env - sem precisar
    saber a senha atual.

.DESCRIPTION
    1) Troca pg_hba.conf pra "trust" temporariamente (conecta sem senha)
    2) Reinicia o servico
    3) Roda ALTER USER postgres WITH PASSWORD 'Vertex2026'
    4) Devolve pg_hba.conf pro scram-sha-256 original
    5) Reinicia o servico de novo

    PRECISA RODAR COMO ADMINISTRADOR (botao direito no PowerShell >
    Executar como administrador > cd ate essa pasta > .\resetar_senha_postgres.ps1)
#>

$ErrorActionPreference = "Stop"

$Servico = "postgresql-x64-17"
$DataDir = "C:\Program Files\PostgreSQL\17\data"
$Psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
$HbaPath = Join-Path $DataDir "pg_hba.conf"
$NovaSenha = "Vertex2026"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Precisa rodar como Administrador. Abra o PowerShell com 'Executar como administrador' e rode de novo." -ForegroundColor Red
    exit 1
}

Write-Host "[1/5] Backup e edicao do pg_hba.conf (trust temporario)..." -ForegroundColor Yellow
Copy-Item $HbaPath "$HbaPath.bak" -Force
$original = Get-Content $HbaPath -Raw
$temporario = $original -replace "scram-sha-256", "trust"
Set-Content -Path $HbaPath -Value $temporario -Encoding ASCII

Write-Host "[2/5] Reiniciando $Servico..." -ForegroundColor Yellow
Restart-Service -Name $Servico -Force
Start-Sleep -Seconds 3

Write-Host "[3/5] Alterando a senha do usuario postgres..." -ForegroundColor Yellow
$env:PGPASSWORD = ""
& $Psql -U postgres -h 127.0.0.1 -p 5432 -c "ALTER USER postgres WITH PASSWORD '$NovaSenha';"

Write-Host "[4/5] Restaurando pg_hba.conf original..." -ForegroundColor Yellow
Set-Content -Path $HbaPath -Value $original -Encoding ASCII

Write-Host "[5/5] Reiniciando $Servico de novo (com autenticacao normal)..." -ForegroundColor Yellow
Restart-Service -Name $Servico -Force

Write-Host "`nPronto! Senha do usuario postgres redefinida pra '$NovaSenha' (a mesma que ja esta em backend\.env)." -ForegroundColor Green
