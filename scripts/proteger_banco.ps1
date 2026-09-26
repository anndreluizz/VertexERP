<#
.SYNOPSIS
    Protege o banco de uma instalacao ANTIGA do Vertex ERP: troca a
    senha fixa "Vertex2026" por uma senha aleatoria so' desta loja e
    passa a exigir senha (scram-sha-256) em vez de "trust".

.DESCRIPTION
    Instalacoes novas ja nascem assim (ver launcher.py::garantir_env).
    As antigas foram criadas com "trust": qualquer programa deste PC
    entra no banco como superusuario sem senha nenhuma.

    1. FECHE o Vertex ERP (no modo Servidor, finalize tambem o
       VertexERP.exe no Gerenciador de Tarefas).
    2. Botao direito neste arquivo > Executar com o PowerShell.

    Antes de mudar qualquer coisa guarda uma copia do .env e do
    pg_hba.conf. Depois de mudar, TESTA a conexao com a senha nova --
    se nao funcionar, volta tudo como estava. Pode rodar de novo sem
    problema (se ja estiver protegido, so' avisa e sai).

    Precisa ficar na pasta do Vertex ERP (do lado do VertexERP.exe).
#>

param(
    # so' pra teste automatizado -- na loja nunca precisa informar
    [string]$Porta = "5442",
    [string]$Raiz = $PSScriptRoot,
    [switch]$SemPerguntar
)

$ErrorActionPreference = "Stop"

$Bin = Join-Path $Raiz "postgres-portable\bin"
$Dados = Join-Path $Raiz "pgdata"
$ArquivoEnv = Join-Path $Raiz ".env"
$Hba = Join-Path $Dados "pg_hba.conf"

function Pausar-E-Sair($codigo) {
    if (-not $SemPerguntar) { Read-Host "`nPressione Enter para fechar" }
    exit $codigo
}

function Senha-Atual {
    $linha = Get-Content $ArquivoEnv | Where-Object { $_ -match "^DB_PASSWORD=(.+)$" } | Select-Object -First 1
    if ($linha) { return ($linha -replace "^DB_PASSWORD=", "").Trim() }
    return "Vertex2026"
}

function Testar-Conexao($senha) {
    # via cmd: no PowerShell 5.1, erro do psql no stderr com
    # ErrorActionPreference=Stop vira excecao -- e aqui a falha e'
    # esperada (testar que SEM senha nao entra)
    $env:PGPASSWORD = $senha
    $psql = Join-Path $Bin "psql.exe"
    cmd /c "`"$psql`" -w -h 127.0.0.1 -p $Porta -U postgres -d postgres -tAc `"SELECT 1`" >nul 2>&1"
    return $LASTEXITCODE -eq 0
}

function Iniciar-Postgres {
    # via cmd com saida pra NUL: o postgres.exe herda o stdout de quem o
    # iniciou -- se for um pipe do PowerShell (| Out-Null, job), o
    # PowerShell fica esperando esse pipe fechar pra sempre e o script
    # trava. Com NUL nao ha pipe nenhum pra esperar.
    $pgctl = Join-Path $Bin "pg_ctl.exe"
    $log = Join-Path $Raiz "pgdata_log.txt"
    cmd /c "`"$pgctl`" -D `"$Dados`" -l `"$log`" -o `"-p $Porta`" -w start >nul 2>&1"
    if ($LASTEXITCODE -ne 0) { throw "Nao consegui iniciar o Postgres (veja pgdata_log.txt)." }
}

function Parar-Postgres {
    $pgctl = Join-Path $Bin "pg_ctl.exe"
    cmd /c "`"$pgctl`" -D `"$Dados`" -m fast stop >nul 2>&1"
}

function Reiniciar-Postgres {
    Parar-Postgres
    Iniciar-Postgres
}

try {
    if (-not (Test-Path (Join-Path $Dados "PG_VERSION"))) {
        throw "Nao achei o banco em $Dados. Este script precisa estar na pasta do Vertex ERP."
    }
    if (-not (Test-Path $ArquivoEnv)) {
        throw "Nao achei o .env em $Raiz."
    }

    $abertos = Get-Process -Name "VertexERP", "VertexERP-Backend", "VertexERP-Frontend" -ErrorAction SilentlyContinue
    if ($abertos -and $Porta -eq "5442") {
        throw "O Vertex ERP ainda esta aberto. Feche o sistema (e finalize VertexERP.exe no Gerenciador de Tarefas) antes de continuar."
    }

    $linhasHba = Get-Content $Hba
    $comTrust = $linhasHba | Where-Object { $_ -notmatch "^\s*#" -and $_ -match "\btrust\s*$" }
    if (-not $comTrust) {
        Write-Host "Este banco ja exige senha. Nada a fazer." -ForegroundColor Green
        Pausar-E-Sair 0
    }

    if (-not $SemPerguntar) {
        $ok = Read-Host "Vai trocar a senha do banco e passar a exigir senha. Digite SIM para continuar"
        if ($ok -ne "SIM") { Write-Host "Cancelado."; Pausar-E-Sair 0 }
    }

    # ---------- subir o Postgres se precisar ----------
    & (Join-Path $Bin "pg_ctl.exe") -D $Dados status | Out-Null
    $subiuAqui = $LASTEXITCODE -ne 0
    if ($subiuAqui) {
        Iniciar-Postgres
    }

    # ---------- copias de seguranca ----------
    $carimbo = Get-Date -Format "yyyyMMdd_HHmmss"
    $copiaEnv = "$ArquivoEnv.antes_proteger_$carimbo"
    $copiaHba = "$Hba.antes_proteger_$carimbo"
    Copy-Item $ArquivoEnv $copiaEnv
    Copy-Item $Hba $copiaHba
    Write-Host "Copias guardadas: $copiaEnv e $copiaHba"

    $senhaAntiga = Senha-Atual
    # 32 caracteres so' letras e numeros (sem simbolo que quebre .env/URL)
    $alfabeto = [char[]]"abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $senhaNova = -join ($bytes | ForEach-Object { $alfabeto[$_ % $alfabeto.Length] })

    try {
        # 1. senha nova no Postgres (ainda em trust, entao entra sem senha)
        $env:PGPASSWORD = $senhaAntiga
        & (Join-Path $Bin "psql.exe") -w -h 127.0.0.1 -p $Porta -U postgres -d postgres -v ON_ERROR_STOP=1 -c "ALTER USER postgres WITH PASSWORD '$senhaNova'" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Nao consegui trocar a senha do usuario postgres." }

        # 2. .env com a senha nova (o backend e o launcher leem daqui)
        $novoEnv = Get-Content $ArquivoEnv | ForEach-Object {
            if ($_ -match "^DB_PASSWORD=") { "DB_PASSWORD=$senhaNova" } else { $_ }
        }
        if (-not ($novoEnv | Where-Object { $_ -match "^DB_PASSWORD=" })) { $novoEnv += "DB_PASSWORD=$senhaNova" }
        Set-Content -Path $ArquivoEnv -Value $novoEnv -Encoding ascii

        # 3. pg_hba: trust -> scram-sha-256
        $novoHba = $linhasHba | ForEach-Object {
            if ($_ -notmatch "^\s*#" -and $_ -match "\btrust\s*$") { $_ -replace "\btrust\s*$", "scram-sha-256" } else { $_ }
        }
        Set-Content -Path $Hba -Value $novoHba -Encoding ascii

        Reiniciar-Postgres

        # 4. conferir: senha nova entra, sem senha NAO entra
        if (-not (Testar-Conexao $senhaNova)) { throw "A senha nova nao funcionou." }
        if (Testar-Conexao "") { throw "O banco ainda aceita entrar sem senha." }
    }
    catch {
        Write-Host "`nAlgo deu errado -- voltando tudo como estava..." -ForegroundColor Yellow
        Copy-Item $copiaEnv $ArquivoEnv -Force
        Copy-Item $copiaHba $Hba -Force
        Reiniciar-Postgres
        $env:PGPASSWORD = ""
        & (Join-Path $Bin "psql.exe") -w -h 127.0.0.1 -p $Porta -U postgres -d postgres -c "ALTER USER postgres WITH PASSWORD '$senhaAntiga'" | Out-Null
        throw
    }
    finally {
        if ($subiuAqui) {
            Parar-Postgres
        }
    }

    Write-Host "`nBANCO PROTEGIDO." -ForegroundColor Green
    Write-Host "A senha nova ficou no .env (nao precisa anotar). Abra o Vertex ERP normalmente."
    Pausar-E-Sair 0
}
catch {
    Write-Host "`nERRO: $($_.Exception.Message)" -ForegroundColor Red
    Pausar-E-Sair 1
}
