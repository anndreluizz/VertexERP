"""Atualizacao dos terminais pela rede da loja: o terminal (PC da
filial, so' o frontend) pergunta a versao do servidor e baixa o
frontend dele daqui -- sem internet nem GitHub. O servidor em si e'
atualizado pelo launcher (atualizador.py)."""

import hashlib
import os
import shutil
import tempfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/atualizacao", tags=["Atualização"])


def _raiz():
    """Pasta da instalacao do servidor (o launcher define); None em dev."""
    return os.getenv("VERTEXERP_INSTALL_DIR") or None


def _versao(raiz):
    try:
        with open(os.path.join(raiz, "versao.txt"), encoding="utf-8-sig") as arquivo:
            return arquivo.read().strip() or None
    except OSError:
        return None


def _sha256(caminho):
    soma = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            soma.update(bloco)
    return soma.hexdigest()


def _pacote(raiz, versao):
    """Zip do VertexERP-Frontend do servidor, montado uma vez por versao
    (escrito em arquivo temporario e renomeado: dois terminais pedindo
    ao mesmo tempo nunca leem um zip pela metade)."""
    pasta = os.path.join(raiz, "atualizacoes")
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, f"terminal_{versao}.zip")
    if not os.path.exists(destino):
        fd, temporario = tempfile.mkstemp(dir=pasta, suffix=".tmp")
        os.close(fd)
        base = temporario[:-4]
        shutil.make_archive(base, "zip", root_dir=raiz, base_dir="VertexERP-Frontend")
        os.remove(temporario)
        os.replace(base + ".zip", destino)
        # so' a versao atual interessa: cada release deixava ~63 MB pra tras
        for nome in os.listdir(pasta):
            if nome.startswith("terminal_") and nome.endswith(".zip") and nome != os.path.basename(destino):
                try:
                    os.remove(os.path.join(pasta, nome))
                except OSError:
                    pass  # terminal ainda baixando esse; sai na proxima versao
    return destino


@router.get("/terminal")
def versao_terminal(usuario=Depends(get_current_user)):
    raiz = _raiz()
    return {"versao": _versao(raiz) if raiz else None}


@router.get("/terminal/pacote")
def pacote_terminal(usuario=Depends(get_current_user)):
    raiz = _raiz()
    versao = _versao(raiz) if raiz else None
    if not versao or not os.path.isdir(os.path.join(raiz, "VertexERP-Frontend")):
        raise HTTPException(status_code=404, detail="Servidor sem pacote de terminal.")
    caminho = _pacote(raiz, versao)
    return FileResponse(
        caminho,
        media_type="application/zip",
        filename=os.path.basename(caminho),
        headers={"X-Versao": versao, "X-Sha256": _sha256(caminho)},
    )
