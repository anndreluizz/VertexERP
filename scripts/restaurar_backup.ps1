<#
.SYNOPSIS
    Restaura um backup (.sql do backup automatico) no banco do Vertex
    ERP deste PC-Servidor.

.DESCRIPTION
    1. FECHE o Vertex ERP neste PC (e, no modo Servidor, finalize o
       VertexERP.exe no Gerenciador de Tarefas).
    2. Botao direito neste arquivo > Executar com o PowerShell.
       (ou: .\restaurar_backup.ps1 -Arquivo "C:\...\vertexerp_2026-09-26_080000.sql")
    3. Escolha o backup na lista (o mais recente e' o 1).

    O banco atual NAO e' apagado: ele e' renomeado para
    vertexerp_antes_restauro_<data> e continua dentro do Postgres. Se a
    restauracao falhar no meio, o script desfaz tudo e volta o banco
    antigo.

    PC NOVO (o antigo quebrou): instale o Vertex ERP, abra UMA vez,
    feche, copie o .sql da nuvem (OneDrive etc.) pra este PC e rode
    este script apontando pra ele.

    Precisa ficar na pasta do Vertex ERP (do lado do VertexERP.exe) --
    montar_pacotes.ps1 ja coloca uma copia la.
#>

param(
    [string]$Arquivo,
    # so' pra teste automatizado (restaurar num Postgres de teste) --
    # na loja nunca precisa informar
    [string]$Porta = "5442",
    [string]$Raiz = $PSScriptRoot,
    [switch]$SemPerguntar
)

$ErrorActionPreference = "Stop"

$Bin = Join-Path $Raiz "postgres-portable\bin"
$Dados = Join-Path $Raiz "pgdata"
$Banco = "vertexerp"

# senha do banco: DB_PASSWORD do .env (instalacoes novas tem senha
# aleatoria); instalacao antiga sem essa linha usa a senha legada --
# mesma regra de launcher.py::_senha_banco
$env:PGPASSWORD = "Vertex2026"
$arquivoEnv = Join-Path $Raiz ".env"
if (Test-Path $arquivoEnv) {
    $linha = Get-Content $arquivoEnv | Where-Object { $_ -match "^DB_PASSWORD=(.+)$" } | Select-Object -First 1
    if ($linha) { $env:PGPASSWORD = ($linha -replace "^DB_PASSWORD=", "").Trim() }
}

function Pausar-E-Sair($codigo) {
    if (-not $SemPerguntar) { Read-Host "`nPressione Enter para fechar" }
    exit $codigo
}

function Rodar($exe, [string[]]$argumentos) {
    & (Join-Path $Bin $exe) @argumentos
    if ($LASTEXITCODE -ne 0) {
        throw "$exe falhou (codigo $LASTEXITCODE)."
    }
}

function Psql([string[]]$argumentos) {
    Rodar "psql.exe" (@("-h", "127.0.0.1", "-p", $Porta, "-U", "postgres", "-v", "ON_ERROR_STOP=1") + $argumentos)
}

try {
    if (-not (Test-Path (Join-Path $Dados "PG_VERSION"))) {
        throw "Nao achei o banco em $Dados. Este script precisa estar na pasta do Vertex ERP, e o Vertex precisa ter sido aberto pelo menos uma vez neste PC."
    }

    # so' importa pro banco do Vertex (porta padrao) -- um Postgres de
    # teste em outra porta nao e' usado pelo sistema aberto
    $abertos = Get-Process -Name "VertexERP", "VertexERP-Backend", "VertexERP-Frontend" -ErrorAction SilentlyContinue
    if ($abertos -and $Porta -eq "5442") {
        throw "O Vertex ERP ainda esta aberto. Feche o sistema (e finalize VertexERP.exe no Gerenciador de Tarefas) antes de restaurar."
    }

    # ---------- escolher o backup ----------
    if (-not $Arquivo) {
        $pasta = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "VertexERP\Backups"
        $lista = @(Get-ChildItem -Path $pasta -Filter "*.sql" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 15)

        if ($lista.Count -eq 0) {
            throw "Nenhum backup encontrado em $pasta. Rode de novo informando o arquivo: .\restaurar_backup.ps1 -Arquivo ""C:\caminho\do\backup.sql"""
        }

        Write-Host "Backups encontrados em ${pasta}:`n"
        for ($i = 0; $i -lt $lista.Count; $i++) {
            $mb = [math]::Round($lista[$i].Length / 1MB, 1)
            Write-Host ("  {0,2}) {1}   ({2} MB)" -f ($i + 1), $lista[$i].Name, $mb)
        }

        $escolha = Read-Host "`nNumero do backup para restaurar (Enter = 1, o mais recente)"
        if (-not $escolha) { $escolha = "1" }
        $Arquivo = $lista[[int]$escolha - 1].FullName
    }

    if (-not (Test-Path $Arquivo)) {
        throw "Arquivo nao encontrado: $Arquivo"
    }

    # ---------- validar: backup cortado no meio nao tem o rodape ----------
    $final = (Get-Content -Path $Arquivo -Tail 10) -join "`n"
    if ($final -notmatch "PostgreSQL database dump complete") {
        throw "Esse arquivo esta incompleto (backup cortado no meio). Escolha outro."
    }

    Write-Host "`nVai restaurar: $Arquivo"
    Write-Host "O banco atual sera guardado como vertexerp_antes_restauro_<data> (nada e' apagado)."
    $ok = if ($SemPerguntar) { "SIM" } else { Read-Host "Digite SIM para continuar" }
    if ($ok -ne "SIM") {
        Write-Host "Cancelado."
        Pausar-E-Sair 0
    }

    # ---------- subir o Postgres (se ja nao estiver de pe) ----------
    & (Join-Path $Bin "pg_ctl.exe") -D $Dados status | Out-Null
    $subiuAqui = $LASTEXITCODE -ne 0

    if ($subiuAqui) {
        # via cmd com saida pra NUL: o postgres.exe herda o stdout de
        # quem o iniciou; se for pipe do PowerShell, o script trava
        # esperando esse pipe fechar
        $pgctl = Join-Path $Bin "pg_ctl.exe"
        $log = Join-Path $Raiz "pgdata_log.txt"
        cmd /c "`"$pgctl`" -D `"$Dados`" -l `"$log`" -o `"-p $Porta`" -w start >nul 2>&1"
        if ($LASTEXITCODE -ne 0) { throw "Nao consegui iniciar o Postgres (veja pgdata_log.txt)." }
    }

    try {
        $existe = & (Join-Path $Bin "psql.exe") -h 127.0.0.1 -p $Porta -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$Banco'"
        $antigo = $null

        if ($existe -eq "1") {
            $antigo = "vertexerp_antes_restauro_" + (Get-Date -Format "yyyyMMdd_HHmmss")
            Psql @("-d", "postgres", "-c", "ALTER DATABASE $Banco RENAME TO $antigo")
            Write-Host "Banco atual guardado como $antigo."
        }

        try {
            Rodar "createdb.exe" @("-h", "127.0.0.1", "-p", $Porta, "-U", "postgres", $Banco)

            Write-Host "Restaurando (pode levar alguns minutos)..."
            # -1: tudo numa transacao so' -- ou restaura inteiro ou nada
            Psql @("-d", $Banco, "-q", "-1", "-f", $Arquivo)
        }
        catch {
            Write-Host "`nFalhou -- desfazendo e voltando o banco anterior..." -ForegroundColor Yellow
            & (Join-Path $Bin "dropdb.exe") -h 127.0.0.1 -p $Porta -U postgres --if-exists $Banco
            if ($antigo) {
                Psql @("-d", "postgres", "-c", "ALTER DATABASE $antigo RENAME TO $Banco")
            }
            throw
        }
    }
    finally {
        if ($subiuAqui) {
            & (Join-Path $Bin "pg_ctl.exe") -D $Dados -m fast stop | Out-Null
        }
    }

    Write-Host "`nRESTAURADO COM SUCESSO." -ForegroundColor Green
    Write-Host "Abra o Vertex ERP normalmente e confira as ultimas vendas."
    if ($antigo) {
        Write-Host "O banco anterior continua guardado como '$antigo' (pode ser apagado depois que tudo estiver conferido)."
    }
    Pausar-E-Sair 0
}
catch {
    Write-Host "`nERRO: $($_.Exception.Message)" -ForegroundColor Red
    Pausar-E-Sair 1
}
