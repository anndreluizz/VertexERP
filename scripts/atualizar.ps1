<#
.SYNOPSIS
    Instala uma versao nova do Vertex ERP no PC-Servidor, com backup e
    volta automatica pra versao anterior se der errado.

.DESCRIPTION
    Vem DENTRO do pacote de atualizacao (Release do GitHub) e e' chamado
    pelo launcher (atualizador.py) depois que a loja clica em "Sim". Roda
    a partir da pasta extraida do pacote ($Pasta) e mexe na instalacao
    ($Raiz):

      1. fecha o Vertex (so' os processos DESTA instalacao);
      2. backup do banco (pg_dump) -- se falhar, nao mexe em nada;
      3. troca VertexERP-Backend, VertexERP-Frontend e VertexERP.exe
         (as atuais ficam como *_antes_atualizacao);
      4. abre de novo e confere se o servidor subiu (ate 2 min);
      5. se NAO subiu: volta as pastas antigas e restaura o backup.

    Tambem da pra rodar na mao (com o Vertex aberto ou fechado):
      powershell -ExecutionPolicy Bypass -File <pacote>\atualizar.ps1
#>

param(
    [string]$Raiz = "C:\servidor",
    [string]$Pasta = $PSScriptRoot,
    # teste: nao abre o Vertex no fim (e nao mostra janelas)
    [switch]$SemIniciar,
    # teste: finge que o servidor novo nao subiu, pra exercitar a volta
    [switch]$SimularFalha
)

$ErrorActionPreference = "Stop"
$Log = Join-Path $Raiz "atualizacao_log.txt"
$Versao = (Get-Content (Join-Path $Pasta "versao.txt") -ErrorAction Stop | Select-Object -First 1).Trim()
$Sufixo = "_antes_atualizacao"
$Porta = 58734

function Log($texto) {
    Add-Content $Log "$(Get-Date -Format s) [$Versao] $texto"
}

function Avisar($texto, [switch]$Erro) {
    Log $texto
    if ($SemIniciar) { return }
    Add-Type -AssemblyName System.Windows.Forms
    $icone = if ($Erro) { "Error" } else { "Information" }
    [System.Windows.Forms.MessageBox]::Show($texto, "Atualização do Vertex ERP", "OK", $icone) | Out-Null
}

function Processos($nome) {
    # so' os desta instalacao -- nunca mexe num Vertex de outra pasta
    Get-Process $nome -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.StartsWith($Raiz, [StringComparison]::OrdinalIgnoreCase) }
}

function Parar-Vertex {
    $janela = Processos "VertexERP-Frontend"
    if ($janela) {
        $janela | ForEach-Object { [void]$_.CloseMainWindow() }
        for ($i = 0; $i -lt 20 -and (Processos "VertexERP-Frontend"); $i++) { Start-Sleep 1 }
        Processos "VertexERP-Frontend" | Stop-Process -Force
    }
    # launcher antes do backend (senao o watchdog dele sobe o backend de novo)
    Processos "VertexERP" | Stop-Process -Force
    Start-Sleep 2
    Processos "VertexERP-Backend" | Stop-Process -Force
    Start-Sleep 3
}

function Ler-Env($chave, $padrao) {
    $linha = Get-Content (Join-Path $Raiz ".env") -ErrorAction SilentlyContinue |
        Where-Object { $_ -like "$chave=*" } | Select-Object -First 1
    if ($linha) { return ($linha -split "=", 2)[1].Trim() }
    return $padrao
}

function Servidor-Subiu {
    for ($i = 0; $i -lt 120; $i++) {
        Start-Sleep 1
        $cliente = New-Object Net.Sockets.TcpClient
        try {
            $cliente.Connect("127.0.0.1", $Porta)
            # ficou de pe: confere de novo depois de um tempo (um backend
            # que cai logo apos subir -- migracao quebrada -- nao conta)
            Start-Sleep 10
            return [bool](Processos "VertexERP-Backend")
        } catch {
        } finally {
            $cliente.Close()
        }
    }
    return $false
}

function Remover($caminho) {
    # Remove-Item nao apaga arquivo com caminho > 260 caracteres (tem
    # varios dentro do _internal do PyInstaller); o prefixo \\?\ aceita
    if (Test-Path $caminho -PathType Container) {
        [IO.Directory]::Delete("\\?\" + (Resolve-Path $caminho).ProviderPath, $true)
    } elseif (Test-Path $caminho) {
        Remove-Item $caminho -Force
    }
}

function Trocar($nome) {
    $atual = Join-Path $Raiz $nome
    $antes = "$atual$Sufixo"
    Remover $antes
    if (Test-Path $atual) { Rename-Item $atual (Split-Path $antes -Leaf) }
    Copy-Item (Join-Path $Pasta $nome) $atual -Recurse
}

function Desfazer($nome) {
    $atual = Join-Path $Raiz $nome
    $antes = "$atual$Sufixo"
    if (-not (Test-Path $antes)) { return }
    Remover $atual
    Rename-Item $antes (Split-Path $atual -Leaf)
}

$itens = "VertexERP-Backend", "VertexERP-Frontend", "VertexERP.exe"

try {
    Log "inicio (instalacao em $Raiz)"
    foreach ($item in $itens) {
        if (-not (Test-Path (Join-Path $Pasta $item))) { throw "Pacote incompleto: falta $item." }
    }

    # 1-2. fecha a janela e faz o backup com o banco ainda no ar
    $env:PGPASSWORD = Ler-Env "DB_PASSWORD" "Vertex2026"
    $portaBanco = Ler-Env "DB_PORT" "5442"
    $pastaBackup = Join-Path $Raiz "atualizacoes"
    New-Item -ItemType Directory -Force $pastaBackup | Out-Null
    $backup = Join-Path $pastaBackup ("antes_{0}_{1}.sql" -f $Versao, (Get-Date -Format "yyyyMMdd_HHmmss"))
    & (Join-Path $Raiz "postgres-portable\bin\pg_dump.exe") -h 127.0.0.1 -p $portaBanco -U postgres -F p -f $backup vertexerp
    if ($LASTEXITCODE -ne 0 -or -not ((Get-Content $backup -Tail 3) -match "dump complete")) {
        throw "O backup do banco falhou -- nada foi alterado."
    }
    Log "backup: $backup"

    Parar-Vertex

    # 3. troca
    $versaoAntes = if (Test-Path (Join-Path $Raiz "versao.txt")) { (Get-Content (Join-Path $Raiz "versao.txt") | Select-Object -First 1) } else { "0" }
    foreach ($item in $itens) { Trocar $item }
    foreach ($script in "restaurar_backup.ps1", "proteger_banco.ps1") {
        if (Test-Path (Join-Path $Pasta $script)) { Copy-Item (Join-Path $Pasta $script) $Raiz -Force }
    }
    if (Test-Path (Join-Path $Pasta "kit")) {
        New-Item -ItemType Directory -Force (Join-Path $Raiz "kit") | Out-Null
        Copy-Item (Join-Path $Pasta "kit\*") (Join-Path $Raiz "kit") -Force
    }
    Set-Content (Join-Path $Raiz "versao.txt") $Versao
    Log "arquivos trocados ($versaoAntes -> $Versao)"

    # 4. abre e confere
    $subiu = $true
    if ($SimularFalha) {
        $subiu = $false
    } elseif (-not $SemIniciar) {
        Start-Process (Join-Path $Raiz "VertexERP.exe") -WorkingDirectory $Raiz
        $subiu = Servidor-Subiu
    }

    if (-not $subiu) {
        # 5. volta tudo
        Log "servidor novo NAO subiu -- voltando a versao $versaoAntes"
        Parar-Vertex
        foreach ($item in $itens) { Desfazer $item }
        Set-Content (Join-Path $Raiz "versao.txt") $versaoAntes
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Raiz "restaurar_backup.ps1") `
            -Arquivo $backup -Raiz $Raiz -Porta $portaBanco -SemPerguntar | Out-Null
        if ($LASTEXITCODE -ne 0) { Log "ATENCAO: restaurar_backup falhou (codigo $LASTEXITCODE); o banco ficou como estava" }
        if (-not $SemIniciar) { Start-Process (Join-Path $Raiz "VertexERP.exe") -WorkingDirectory $Raiz }
        Avisar ("A atualização para a versão $Versao não deu certo e o sistema voltou " +
                "sozinho para a versão anterior. Nada foi perdido. (Detalhes em atualizacao_log.txt)") -Erro
        exit 2
    }

    # kit de emergencia no OneDrive acompanha a versao nova
    $kit = Join-Path $Raiz "kit\atualizar_kit.ps1"
    if ((Test-Path $kit) -and -not $SemIniciar) {
        try { & $kit -Origem $Raiz } catch { Log "kit nao atualizado: $_" }
    }

    Avisar "Vertex ERP atualizado para a versão $Versao."
    exit 0
} catch {
    Log "ERRO: $_"
    # se ja tinha fechado o Vertex, abre de novo (com o que estiver la)
    if (-not $SemIniciar -and -not (Processos "VertexERP")) {
        Start-Process (Join-Path $Raiz "VertexERP.exe") -WorkingDirectory $Raiz
    }
    Avisar "Não foi possível atualizar o Vertex ERP: $_" -Erro
    exit 1
}
