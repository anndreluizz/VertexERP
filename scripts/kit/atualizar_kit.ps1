<#
.SYNOPSIS
    Mantem o kit de emergencia (OneDrive\VertexERP-Kit) igual ao
    programa que esta rodando neste PC-Servidor.

.DESCRIPTION
    Roda sozinho todo dia (tarefa agendada "VertexERP Kit", criada por
    instalar_kit.ps1) e depois de cada atualizacao. So copia o que mudou
    (robocopy /MIR), entao normalmente leva segundos.

    NAO vai pro kit: o banco (pgdata -- os backups ja estao em
    VertexERP-Backups), o .env (senhas deste PC) e as pastas *_antes_*
    de rollback.
#>

param(
    [string]$Origem = "C:\servidor",
    [string]$Kit = (Join-Path $env:OneDrive "VertexERP-Kit")
)

$ErrorActionPreference = "Stop"
$log = Join-Path $Origem "kit_log.txt"

try {
    $programa = Join-Path $Kit "programa"
    New-Item -ItemType Directory -Force $programa | Out-Null

    foreach ($pasta in "VertexERP-Backend", "VertexERP-Frontend", "postgres-portable") {
        robocopy (Join-Path $Origem $pasta) (Join-Path $programa $pasta) /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy $pasta falhou ($LASTEXITCODE)." }
    }

    foreach ($arquivo in "VertexERP.exe", "icone.ico", "INSTALAR.md", "restaurar_backup.ps1",
                         "fechar_vertex.ps1", "reiniciar_vertex.ps1", "excluir_do_defender.ps1",
                         "proteger_banco.ps1") {
        $caminho = Join-Path $Origem $arquivo
        if (Test-Path $caminho) { Copy-Item $caminho $programa -Force }
    }

    # certificado HTTPS: com ele o servidor novo tem a mesma "identidade"
    # e os celulares/caixas nao estranham a troca
    robocopy (Join-Path $Origem "certs") (Join-Path $Kit "certs") /MIR /NFL /NDL /NJH /NJS /NP | Out-Null

    # os scripts do proprio kit ficam do lado deste arquivo
    foreach ($arquivo in "VIRAR_SERVIDOR.ps1", "LEIA-ME.txt") {
        Copy-Item (Join-Path $PSScriptRoot $arquivo) $Kit -Force
    }

    Set-Content (Join-Path $Kit "versao.txt") (
        "Kit atualizado em $(Get-Date -Format 'dd/MM/yyyy HH:mm') a partir de $env:COMPUTERNAME"
    )
    Add-Content $log "$(Get-Date -Format s) OK"
} catch {
    Add-Content $log "$(Get-Date -Format s) ERRO: $_"
    throw
}
