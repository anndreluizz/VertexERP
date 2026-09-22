<#
.SYNOPSIS
    Adiciona a pasta de instalacao do Vertex ERP como excecao do
    Windows Defender -- mitiga a abertura muito lenta (ou travada) que
    acontece logo apos copiar/atualizar os arquivos, quando o Defender
    escaneia via nuvem (Cloud Protection/Block-at-First-Sight) cada
    .exe recem-escrito e ainda sem reputacao antes de deixar rodar.

.DESCRIPTION
    Roda UMA VEZ por instalacao (Servidor ou Terminal), depois de
    copiar a pasta pro PC de destino -- nao precisa rodar de novo a
    cada abertura normal do sistema, so depois de reinstalar/mover a
    pasta pra outro lugar, OU depois de trocar os .exe (rebuild/deploy
    novo -- ver nota sobre Tamper Protection abaixo: a excecao e' por
    CAMINHO, entao sobrevive a troca dos arquivos, mas so' se ela
    realmente tiver sido aplicada da primeira vez). So mitiga a
    demora: nao substitui assinar os executaveis (mais correto a longo
    prazo, mas exige certificado pago + token de hardware/HSM, ver
    docs/06-roadmap.md).

    PRECISA RODAR COMO ADMINISTRADOR (botao direito no arquivo >
    Executar com o PowerShell > se pedir, escolha "Sim" na tela do UAC
    -- ou: botao direito no PowerShell > Executar como administrador >
    cd ate essa pasta > .\excluir_do_defender.ps1)
#>

$ErrorActionPreference = "Stop"

# a propria pasta onde este script foi copiado -- ver montar_pacotes.ps1,
# que coloca uma copia dele dentro de cada pacote (Servidor/ e
# Terminal/), lado a lado com o VertexERP.exe/VertexERP-Frontend.exe
$PastaInstalacao = $PSScriptRoot

$Executaveis = @(
    (Join-Path $PastaInstalacao "VertexERP.exe"),
    (Join-Path $PastaInstalacao "VertexERP-Backend\VertexERP-Backend.exe"),
    (Join-Path $PastaInstalacao "VertexERP-Frontend\VertexERP-Frontend.exe")
) | Where-Object { Test-Path $_ }

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Precisa rodar como Administrador." -ForegroundColor Red
    Write-Host "Botao direito neste arquivo > Executar com o PowerShell (aceite o UAC)," -ForegroundColor Red
    Write-Host "ou abra o PowerShell como Administrador e rode de novo a partir desta pasta." -ForegroundColor Red
    exit 1
}

try {
    Get-Command Add-MpPreference -ErrorAction Stop | Out-Null
} catch {
    Write-Host "Nao encontrei o Windows Defender neste PC (Add-MpPreference indisponivel)." -ForegroundColor Red
    Write-Host "Se este PC usa outro antivirus, adicione '$PastaInstalacao' como excecao por la." -ForegroundColor Red
    exit 1
}

Write-Host "Adicionando '$PastaInstalacao' como excecao do Windows Defender..." -ForegroundColor Yellow

# Excecao por PASTA (cobre qualquer .exe novo que aparecer ali, ex.:
# apos um rebuild/deploy) e por PROCESSO (cinto e suspensorio -- em
# alguns PCs o Cloud Protection ainda escaneia um processo pelo nome
# mesmo com o caminho excluido, dependendo da politica aplicada).
# Cada Add-MpPreference roda isolado: se um tipo de excecao falhar
# (raro, mas acontece por politica), o outro ainda tenta.
$falhaCaminho = $null
$falhaProcesso = $null

try {
    Add-MpPreference -ExclusionPath $PastaInstalacao -ErrorAction Stop
} catch {
    $falhaCaminho = $_
}

foreach ($exe in $Executaveis) {
    try {
        Add-MpPreference -ExclusionProcess $exe -ErrorAction Stop
    } catch {
        $falhaProcesso = $_
    }
}

# ==========================================
# VERIFICACAO -- Add-MpPreference pode "dar certo" sem erro nenhum e
# mesmo assim NAO aplicar nada, se o Tamper Protection do Windows
# estiver ligado (padrao no Windows 11 desde 2019/2020). Nesse caso,
# so' mudancas feitas pela propria janela "Seguranca do Windows"
# contam -- PowerShell/registro sao bloqueados em silencio. Sem essa
# checagem, o script dizia "Pronto!" e a exclusao nunca tinha sido
# aplicada de verdade, e o problema voltava no proximo rebuild sem
# nenhum aviso.
# ==========================================

$prefsAtuais = Get-MpPreference
$caminhoAplicado = $prefsAtuais.ExclusionPath -contains $PastaInstalacao
$algumProcessoAplicado = $false

foreach ($exe in $Executaveis) {
    if ($prefsAtuais.ExclusionProcess -contains $exe) {
        $algumProcessoAplicado = $true
    }
}

if ($caminhoAplicado -or $algumProcessoAplicado) {
    Write-Host "`nPronto! Confirmado: a exclusao foi aplicada de verdade (conferido lendo de volta a config do Defender)." -ForegroundColor Green
    Write-Host "O Defender nao vai mais escanear os arquivos dessa pasta a cada abertura." -ForegroundColor Green
    Write-Host "Se voce reinstalar/mover o Vertex ERP pra outra pasta, rode este script de novo la." -ForegroundColor Green
} else {
    Write-Host "`nATENCAO: o comando rodou sem erro, mas a exclusao NAO apareceu na configuracao do Defender ao conferir de volta." -ForegroundColor Red
    Write-Host "Isso normalmente significa que o 'Tamper Protection' (Protecao contra adulteracao) esta ligado neste PC --" -ForegroundColor Red
    Write-Host "ele bloqueia silenciosamente mudancas de exclusao feitas por PowerShell/script, so aceita pela propria janela do Windows." -ForegroundColor Red
    Write-Host "`nAdicione a exclusao NA MAO, pela janela do Windows (sempre funciona, mesmo com Tamper Protection ligado):" -ForegroundColor Yellow
    Write-Host "  1. Abra 'Seguranca do Windows' (pesquise no menu Iniciar)" -ForegroundColor Yellow
    Write-Host "  2. Protecao contra virus e ameacas > Gerenciar configuracoes (embaixo de 'Configuracoes de protecao contra virus e ameacas')" -ForegroundColor Yellow
    Write-Host "  3. Role ate 'Exclusoes' > Adicionar ou remover exclusoes > Adicionar uma exclusao > Pasta" -ForegroundColor Yellow
    Write-Host "  4. Selecione: $PastaInstalacao" -ForegroundColor Yellow
    if ($falhaCaminho) {
        Write-Host "`n(Detalhe do erro ao tentar por caminho: $($falhaCaminho.Exception.Message))" -ForegroundColor DarkGray
    }
    if ($falhaProcesso) {
        Write-Host "(Detalhe do erro ao tentar por processo: $($falhaProcesso.Exception.Message))" -ForegroundColor DarkGray
    }
    exit 1
}
