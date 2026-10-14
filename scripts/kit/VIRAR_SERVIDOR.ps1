<#
.SYNOPSIS
    Transforma ESTE computador no servidor do Vertex ERP, a partir do kit
    de emergencia no OneDrive (use quando o PC-Servidor da loja quebrar).

.DESCRIPTION
    Botao direito > Executar com o PowerShell (de preferencia como
    administrador, pra liberar o firewall pros outros caixas).

    1. Copia o programa do kit pra C:\servidor (recusa se ja tiver um
       banco la -- nunca sobrescreve um servidor que existe).
    2. Copia os certificados (os celulares e caixas continuam confiando
       no servidor, sem reconfigurar nada).
    3. Cria o banco e restaura o backup MAIS RECENTE da pasta
       VertexERP-Backups (do lado do kit, no OneDrive).
    4. Cria os atalhos (Area de Trabalho e Inicializar) e abre o Vertex.

    Depois: ver LEIA-ME.txt (Tailscale e endereco dos outros caixas).
#>

param(
    [string]$Destino = "C:\servidor",
    # so' pra teste (simulado em outra pasta/porta sem mexer em nada)
    [string]$Porta = "5442",
    [string]$Backup,
    [switch]$SemIniciar
)

$ErrorActionPreference = "Stop"

$Kit = $PSScriptRoot
$Programa = Join-Path $Kit "programa"
$PastaBackups = Join-Path (Split-Path $Kit -Parent) "VertexERP-Backups"

function Passo($texto) { Write-Host "`n== $texto" -ForegroundColor Cyan }

function Sair($codigo) {
    if (-not $SemIniciar) { Read-Host "`nPressione Enter para fechar" }
    exit $codigo
}

try {
    Passo "Conferindo o kit"
    if (-not (Test-Path (Join-Path $Programa "VertexERP.exe"))) {
        throw "Nao achei o programa em $Programa. O kit esta incompleto."
    }
    if (Test-Path (Join-Path $Destino "pgdata")) {
        throw "Ja existe um banco em $Destino\pgdata. Este PC ja e' um servidor -- nada foi alterado."
    }

    if (-not $Backup) {
        $Backup = Get-ChildItem $PastaBackups -Filter "vertexerp_*.sql" -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $Backup -or -not (Test-Path $Backup)) {
        throw "Nao achei nenhum backup (vertexerp_*.sql) em $PastaBackups."
    }
    # backup cortado no meio nao serve (mesma checagem do launcher)
    $final = Get-Content $Backup -Tail 5 -Encoding UTF8
    if (-not ($final -match "PostgreSQL database dump complete")) {
        throw "O backup $Backup esta incompleto. Rode de novo com -Backup apontando pra um anterior."
    }
    Write-Host "Backup que sera restaurado: $(Split-Path $Backup -Leaf)"

    Passo "Copiando o programa pra $Destino (pode demorar: o OneDrive baixa os arquivos)"
    New-Item -ItemType Directory -Force $Destino | Out-Null
    robocopy $Programa $Destino /E /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Falha ao copiar o programa (robocopy $LASTEXITCODE)." }
    $certsKit = Join-Path $Kit "certs"
    if (Test-Path $certsKit) {
        robocopy $certsKit (Join-Path $Destino "certs") /E /NFL /NDL /NJH /NJS /NP | Out-Null
    }

    Passo "Configurando (.env)"
    $senha = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
    $chave = -join (1..64 | ForEach-Object { "{0:x}" -f (Get-Random -Maximum 16) })
    $linhas = @(
        "APP_NAME=Vertex ERP", "APP_VERSION=1.0.0", "",
        "DB_HOST=127.0.0.1", "DB_PORT=$Porta", "DB_NAME=vertexerp",
        "DB_USER=postgres", "DB_PASSWORD=$senha", "",
        "VERTEXERP_HOST=0.0.0.0", "",
        "SECRET_KEY=$chave", "JWT_ALGORITHM=HS256", "ACCESS_TOKEN_EXPIRE_MINUTES=60", "",
        "VERTEXERP_BACKUP_EXTRA=$PastaBackups"
    )
    $firebase = Join-Path $PastaBackups "firebase-credentials.json"
    if (Test-Path $firebase) {
        Copy-Item $firebase (Join-Path $Destino "certs\firebase-credentials.json") -Force
        $linhas += "FIREBASE_CREDENTIALS_PATH=$(Join-Path $Destino 'certs\firebase-credentials.json')"
    }
    [IO.File]::WriteAllLines((Join-Path $Destino ".env"), $linhas)

    Passo "Criando o banco e restaurando o backup"
    $bin = Join-Path $Destino "postgres-portable\bin"
    $dados = Join-Path $Destino "pgdata"
    $arquivoSenha = New-TemporaryFile
    [IO.File]::WriteAllText($arquivoSenha, $senha)
    try {
        & "$bin\initdb.exe" -D $dados -U postgres --pwfile $arquivoSenha -A scram-sha-256 -E UTF8 --locale=C | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "initdb falhou." }
    } finally { Remove-Item $arquivoSenha -Force }

    $env:PGPASSWORD = $senha
    # Sobe sem esperar e pergunta ao pg_isready. Esperar o pg_ctl trava o
    # script pra sempre: o postgres e' filho dele e herda a saida (com
    # "& pg_ctl | Out-Null") ou entra na espera (Start-Process -Wait).
    Start-Process "$bin\pg_ctl.exe" -WindowStyle Hidden -ArgumentList @(
        "-D", "`"$dados`"", "-l", "`"$(Join-Path $Destino 'pgdata_log.txt')`"", "-o", "`"-p $Porta`"", "start"
    ) | Out-Null
    $pronto = $false
    for ($i = 0; $i -lt 60 -and -not $pronto; $i++) {
        Start-Sleep 1
        & "$bin\pg_isready.exe" -h 127.0.0.1 -p $Porta -q
        $pronto = ($LASTEXITCODE -eq 0)
    }
    if (-not $pronto) { throw "O Postgres nao subiu em 60s (ver pgdata_log.txt)." }
    try {
        & "$bin\createdb.exe" -h 127.0.0.1 -p $Porta -U postgres vertexerp
        if ($LASTEXITCODE -ne 0) { throw "createdb falhou." }
        & "$bin\psql.exe" -h 127.0.0.1 -p $Porta -U postgres -d vertexerp -q -v ON_ERROR_STOP=1 -f $Backup | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "A restauracao do backup falhou." }
        $resumo = & "$bin\psql.exe" -h 127.0.0.1 -p $Porta -U postgres -d vertexerp -At -c `
            "select (select count(*) from clientes) || ' clientes, ' || (select count(*) from vendas) || ' vendas, ' || (select count(*) from contas_pagar) || ' contas a pagar'"
        Write-Host "Restaurado: $resumo" -ForegroundColor Green
    } finally {
        & "$bin\pg_ctl.exe" -D $dados -m fast stop | Out-Null
    }

    if ($SemIniciar) { Write-Host "`nOK (teste: atalhos e firewall nao foram criados)."; exit 0 }

    Passo "Atalhos"
    $shell = New-Object -ComObject WScript.Shell
    foreach ($pasta in @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Startup"))) {
        $atalho = $shell.CreateShortcut((Join-Path $pasta "Vertex ERP.lnk"))
        $atalho.TargetPath = Join-Path $Destino "VertexERP.exe"
        $atalho.WorkingDirectory = $Destino
        $atalho.IconLocation = Join-Path $Destino "icone.ico"
        $atalho.Save()
    }

    Passo "Firewall (pros outros caixas e o celular conectarem)"
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
    if ($admin) {
        netsh advfirewall firewall add rule name="Vertex ERP" dir=in action=allow protocol=TCP localport=58734 | Out-Null
        Write-Host "Porta 58734 liberada."
    } else {
        Write-Host "Nao rodou como administrador: se o Windows perguntar sobre o firewall ao abrir o Vertex, clique em PERMITIR." -ForegroundColor Yellow
    }

    Passo "Abrindo o Vertex ERP"
    Start-Process (Join-Path $Destino "VertexERP.exe") -WorkingDirectory $Destino
    Write-Host "`nPRONTO. Agora siga o LEIA-ME.txt (Tailscale e endereco dos caixas)." -ForegroundColor Green
    Sair 0
} catch {
    Write-Host "`nERRO: $_" -ForegroundColor Red
    Sair 1
}
