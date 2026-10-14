"""Atualizacao automatica pelo GitHub (usado pelo launcher.py).

Cada merge no main com o CI verde vira uma Release no GitHub (ver
.github/workflows/release.yml) com o pacote zipado + o sha256 dele. O
launcher pergunta de tempos em tempos se tem versao nova; se tiver,
pergunta pra loja "Atualizar agora?" e, no Sim, baixa, confere o hash,
extrai e chama o atualizar.ps1 DO PACOTE NOVO (backup do banco, troca
das pastas, reabre, volta sozinho pra versao anterior se der errado).

Tudo aqui e' best-effort: sem internet, GitHub fora do ar etc. so' vai
pro atualizacao_log.txt -- nunca pode atrapalhar a loja de vender.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import zipfile
from datetime import date, datetime

REPOSITORIO = "anndreluizz/VertexERP"
URL_ULTIMA_VERSAO = f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"

ARQUIVO_VERSAO = "versao.txt"
ARQUIVO_ADIADO = "atualizacao_adiada.txt"
ARQUIVO_LOG = "atualizacao_log.txt"
PASTA_ATUALIZACOES = "atualizacoes"

ESPERA_INICIAL_SEGUNDOS = 5 * 60
INTERVALO_SEGUNDOS = 6 * 60 * 60

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def _log(base, texto):
    try:
        with open(os.path.join(base, ARQUIVO_LOG), "a", encoding="utf-8") as arquivo:
            arquivo.write(f"{datetime.now().isoformat(timespec='seconds')} {texto}\n")
    except OSError:
        pass


def versao_local(base):
    """Versao instalada (versao.txt, escrito pelo atualizar.ps1). Sem o
    arquivo = instalacao de antes da atualizacao automatica: "0", que
    perde pra qualquer versao publicada."""
    try:
        with open(os.path.join(base, ARQUIVO_VERSAO), encoding="utf-8") as arquivo:
            return arquivo.read().strip() or "0"
    except OSError:
        return "0"


def _numeros(versao):
    return tuple(int(n) for n in re.findall(r"\d+", versao or ""))


def eh_mais_nova(remota, local):
    return _numeros(remota) > _numeros(local)


def buscar_ultima_versao(abrir=urllib.request.urlopen):
    """{"versao", "url_zip", "url_sha256", "notas"} da ultima Release,
    ou None se ela nao tiver o pacote."""
    pedido = urllib.request.Request(
        URL_ULTIMA_VERSAO,
        headers={"User-Agent": "VertexERP-launcher", "Accept": "application/vnd.github+json"},
    )
    with abrir(pedido, timeout=20) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))

    urls = {a["name"]: a["browser_download_url"] for a in dados.get("assets", [])}
    zips = [nome for nome in urls if nome.endswith(".zip")]
    if not zips or f"{zips[0]}.sha256" not in urls:
        return None
    return {
        "versao": dados["tag_name"].lstrip("v"),
        "url_zip": urls[zips[0]],
        "url_sha256": urls[f"{zips[0]}.sha256"],
        "notas": (dados.get("body") or "").strip(),
    }


def _baixar(url, destino, abrir=urllib.request.urlopen):
    pedido = urllib.request.Request(url, headers={"User-Agent": "VertexERP-launcher"})
    temporario = destino + ".parcial"
    with abrir(pedido, timeout=60) as resposta, open(temporario, "wb") as arquivo:
        shutil.copyfileobj(resposta, arquivo, 1024 * 1024)
    os.replace(temporario, destino)


def _sha256(caminho):
    soma = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            soma.update(bloco)
    return soma.hexdigest()


def preparar_pacote(base, release, abrir=urllib.request.urlopen):
    """Baixa, confere o sha256 e extrai. Devolve a pasta extraida (com o
    atualizar.ps1 e o programa novo dentro)."""
    pasta_atualizacoes = os.path.join(base, PASTA_ATUALIZACOES)
    os.makedirs(pasta_atualizacoes, exist_ok=True)
    versao = release["versao"]
    zip_destino = os.path.join(pasta_atualizacoes, f"VertexERP-{versao}.zip")
    pasta = os.path.join(pasta_atualizacoes, versao)

    _baixar(release["url_zip"], zip_destino, abrir)
    sha_destino = zip_destino + ".sha256"
    _baixar(release["url_sha256"], sha_destino, abrir)
    with open(sha_destino, encoding="utf-8") as arquivo:
        esperado = arquivo.read().split()[0].strip().lower()
    os.remove(sha_destino)

    if _sha256(zip_destino) != esperado:
        os.remove(zip_destino)
        raise RuntimeError("O arquivo da atualizacao veio corrompido (sha256 nao confere).")

    if os.path.isdir(pasta):
        shutil.rmtree(pasta)
    with zipfile.ZipFile(zip_destino) as pacote:
        pacote.extractall(pasta)
    os.remove(zip_destino)

    if not os.path.exists(os.path.join(pasta, "atualizar.ps1")):
        raise RuntimeError("Pacote de atualizacao sem o atualizar.ps1.")

    # so' guarda as 2 ultimas versoes extraidas
    antigas = sorted(
        (p for p in os.listdir(pasta_atualizacoes)
         if os.path.isdir(os.path.join(pasta_atualizacoes, p)) and p != versao),
        key=_numeros,
    )
    for antiga in antigas[:-1]:
        shutil.rmtree(os.path.join(pasta_atualizacoes, antiga), ignore_errors=True)

    return pasta


def iniciar_instalacao(base, pasta):
    """Chama o atualizar.ps1 do pacote novo, solto do launcher (ele
    fecha o launcher no meio da troca)."""
    subprocess.Popen(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-WindowStyle", "Hidden",
            "-File", os.path.join(pasta, "atualizar.ps1"),
            "-Raiz", base,
        ],
        cwd=pasta,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


def _adiada_hoje(base):
    try:
        with open(os.path.join(base, ARQUIVO_ADIADO), encoding="utf-8") as arquivo:
            return arquivo.read().strip() == date.today().isoformat()
    except OSError:
        return False


def verificar_uma_vez(base, perguntar, avisar_erro, buscar=buscar_ultima_versao,
                      preparar=preparar_pacote, instalar=iniciar_instalacao):
    """Uma rodada: devolve True se disparou a instalacao."""
    if _adiada_hoje(base):
        return False

    try:
        release = buscar()
    except Exception as erro:  # sem internet etc. -- tenta de novo depois
        _log(base, f"nao consegui consultar o GitHub: {erro}")
        return False

    local = versao_local(base)
    if not release or not eh_mais_nova(release["versao"], local):
        return False

    notas = release["notas"][:600]
    if not perguntar(
        "Atualização do Vertex ERP",
        f"Tem uma versão nova do Vertex ERP ({release['versao']}).\n\n"
        + (f"{notas}\n\n" if notas else "")
        + "Atualizar agora?\n\n"
        "O sistema fecha por cerca de 1 minuto e abre sozinho. Antes, é "
        "feito um backup do banco; se der algum problema, ele volta "
        "sozinho para a versão atual.\n\n"
        "(Não = pergunta de novo amanhã.)",
    ):
        with open(os.path.join(base, ARQUIVO_ADIADO), "w", encoding="utf-8") as arquivo:
            arquivo.write(date.today().isoformat())
        _log(base, f"versao {release['versao']} adiada pela loja")
        return False

    try:
        _log(base, f"baixando versao {release['versao']} (instalada: {local})")
        pasta = preparar(base, release)
        instalar(base, pasta)
        _log(base, f"instalacao da {release['versao']} iniciada")
        return True
    except Exception as erro:
        _log(base, f"falha ao preparar a {release['versao']}: {erro}")
        avisar_erro(
            "Atualização do Vertex ERP",
            f"Não consegui baixar a atualização agora:\n\n{erro}\n\n"
            "O sistema continua funcionando normalmente. Tento de novo mais tarde.",
        )
        return False


def iniciar_verificacao(base, perguntar, avisar_erro):
    def laco():
        time.sleep(ESPERA_INICIAL_SEGUNDOS)
        while True:
            if verificar_uma_vez(base, perguntar, avisar_erro):
                return
            time.sleep(INTERVALO_SEGUNDOS)

    threading.Thread(target=laco, daemon=True).start()
