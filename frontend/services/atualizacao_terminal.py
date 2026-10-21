"""Atualizacao do TERMINAL (PC so' com o frontend, ex.: filial): compara
a versao dele com a do servidor e, se estiver atrasado, baixa o frontend
do proprio servidor da loja e se troca. O PC-servidor nao usa isto --
quem atualiza ele e' o launcher (atualizador.py).

Layout igual nos dois: <raiz>/VertexERP-Frontend/VertexERP-Frontend.exe
e <raiz>/versao.txt."""

import hashlib
import os
import subprocess
import sys
import tempfile
import zipfile

import requests

from services import api

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
PASTA = "VertexERP-Frontend"


def raiz_terminal():
    """Pasta raiz do terminal, ou None quando nao se aplica (rodando do
    codigo-fonte, ou no PC-servidor, que tem o backend ao lado)."""
    if not getattr(sys, "frozen", False):
        return None
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(sys.executable)))
    if os.path.isdir(os.path.join(raiz, "VertexERP-Backend")):
        return None
    return raiz


def versao_local(raiz):
    try:
        with open(os.path.join(raiz, "versao.txt"), encoding="utf-8-sig") as arquivo:
            return arquivo.read().strip() or "0"
    except OSError:
        return "0"


def _numeros(versao):
    return tuple(int(p) for p in str(versao).split(".") if p.isdigit())


def eh_mais_nova(remota, local):
    return _numeros(remota) > _numeros(local)


def versao_disponivel():
    """Versao do servidor se for mais nova que a deste terminal; senao
    None. Roda na worker thread."""
    raiz = raiz_terminal()
    if raiz is None:
        return None
    resposta = api.get("/atualizacao/terminal")
    if resposta.status_code != 200:
        return None
    remota = resposta.json().get("versao")
    if remota and eh_mais_nova(remota, versao_local(raiz)):
        return remota
    return None


def baixar_e_preparar(versao):
    """Baixa o zip do servidor, confere o sha256 e extrai ao lado da
    instalacao. Devolve o caminho do script que faz a troca. Roda na
    worker thread."""
    raiz = raiz_terminal()
    destino = os.path.join(raiz, "atualizacoes", versao)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    zip_local = os.path.join(tempfile.gettempdir(), f"vertex_terminal_{versao}.zip")

    resposta = api._requisitar(
        requests.get, api.URL + "/atualizacao/terminal/pacote",
        headers={"Authorization": f"Bearer {api.TOKEN}"},
        stream=True, timeout=(10, 600),
    )
    if resposta.status_code != 200:
        raise Exception(f"O servidor não entregou a atualização (HTTP {resposta.status_code}).")
    soma = hashlib.sha256()
    with open(zip_local, "wb") as arquivo:
        for bloco in resposta.iter_content(1024 * 1024):
            arquivo.write(bloco)
            soma.update(bloco)
    if soma.hexdigest() != resposta.headers.get("X-Sha256"):
        os.remove(zip_local)
        raise Exception("A atualização veio corrompida (sha256 não confere).")

    with zipfile.ZipFile(zip_local) as pacote:
        pacote.extractall(destino)
    os.remove(zip_local)
    if not os.path.isfile(os.path.join(destino, PASTA, f"{PASTA}.exe")):
        raise Exception("Pacote de atualização incompleto.")

    script = os.path.join(raiz, "atualizacoes", "trocar_terminal.ps1")
    with open(script, "w", encoding="utf-8-sig") as arquivo:
        arquivo.write(_SCRIPT_TROCA)
    return script, destino, versao


# espera o Vertex fechar, guarda a versao atual em *_antes_atualizacao,
# poe a nova no lugar e abre de novo; se a troca falhar, volta a antiga
_SCRIPT_TROCA = r'''param([string]$Raiz, [string]$Nova, [string]$Versao, [int]$ProcessoId)
$ErrorActionPreference = "Stop"
$Log = Join-Path $Raiz "atualizacao_log.txt"
function Log($t) { Add-Content $Log "$(Get-Date -Format s) [terminal $Versao] $t" }
function Remover($c) { if (Test-Path $c) { [IO.Directory]::Delete("\\?\" + (Resolve-Path $c).ProviderPath, $true) } }
try {
    Log "inicio"
    $atual = Join-Path $Raiz "VertexERP-Frontend"
    for ($i = 0; $i -lt 60 -and (Get-Process -Id $ProcessoId -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
    # fecha tambem as outras janelas do Vertex abertas nessa pasta, senao elas travam a troca
    Get-Process | Where-Object { $_.Path -like "$atual\*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 2
    $antes = "$atual" + "_antes_atualizacao"
    Remover $antes
    Rename-Item $atual (Split-Path $antes -Leaf)
    try {
        Move-Item (Join-Path $Nova "VertexERP-Frontend") $atual
    } catch {
        Rename-Item $antes (Split-Path $atual -Leaf)
        throw
    }
    Set-Content (Join-Path $Raiz "versao.txt") $Versao -Encoding ASCII
    Remover $Nova
    Log "atualizado"
} catch {
    Log "falhou: $_"
}
Start-Process (Join-Path $Raiz "VertexERP-Frontend\VertexERP-Frontend.exe")
'''


def iniciar_troca(script, destino, versao):
    """Solta o script da troca (ele espera este processo fechar)."""
    subprocess.Popen(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-WindowStyle", "Hidden", "-File", script,
            "-Raiz", raiz_terminal(), "-Nova", destino,
            "-Versao", versao, "-ProcessoId", str(os.getpid()),
        ],
        creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
        # fora da pasta do Vertex: herdando ela, o proprio script a deixa
        # "em uso" e o Rename-Item da troca falha sempre
        cwd=tempfile.gettempdir(),
    )
