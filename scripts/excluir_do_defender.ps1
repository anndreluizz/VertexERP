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
    pasta pra outro lugar. So mitiga a demora: nao substitui assinar
    os executaveis (mais correto a longo prazo, mas exige certificado
    pago + token de hardware/HSM, ver docs/06-roadmap.md).

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

Add-MpPreference -ExclusionPath $PastaInstalacao

Write-Host "`nPronto! O Defender nao vai mais escanear os arquivos dessa pasta a cada abertura." -ForegroundColor Green
Write-Host "Se voce reinstalar/mover o Vertex ERP pra outra pasta, rode este script de novo la." -ForegroundColor Green
