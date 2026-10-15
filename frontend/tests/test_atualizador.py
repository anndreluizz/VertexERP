"""Atualizacao automatica do launcher (atualizador.py, na raiz -- fica
aqui porque este e' o job de CI que roda em Windows). Uma atualizacao
errada derruba a loja: comparacao de versao, hash e o "Nao" da loja nao
podem regredir calados."""

import hashlib
import importlib.util
import io
import json
import os
import time
import zipfile
from datetime import date

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def atualizador():
    spec = importlib.util.spec_from_file_location(
        "atualizador", os.path.join(_RAIZ, "atualizador.py")
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_compara_versao_por_numero_nao_por_texto(atualizador):
    assert atualizador.eh_mais_nova("2026.10.14.10", "2026.10.14.9")
    assert atualizador.eh_mais_nova("2026.10.15.1", "2026.10.14.99")
    assert not atualizador.eh_mais_nova("2026.10.14.1", "2026.10.14.1")
    # instalacao sem versao.txt aceita qualquer versao publicada
    assert atualizador.eh_mais_nova("2026.10.14.1", "0")


def test_versao_local_sem_arquivo_e_zero(atualizador, tmp_path):
    assert atualizador.versao_local(str(tmp_path)) == "0"
    (tmp_path / "versao.txt").write_text("2026.10.14.3\n")
    assert atualizador.versao_local(str(tmp_path)) == "2026.10.14.3"


def _resposta(conteudo):
    class Resposta(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    return Resposta(conteudo)


def _release(zip_bytes, sha=None):
    sha = sha or hashlib.sha256(zip_bytes).hexdigest()
    dados = {
        "tag_name": "v2026.10.14.5",
        "body": "Caixa com fiado separado",
        "assets": [
            {"name": "VertexERP-2026.10.14.5.zip", "browser_download_url": "https://x/zip"},
            {"name": "VertexERP-2026.10.14.5.zip.sha256", "browser_download_url": "https://x/sha"},
        ],
    }
    arquivos = {
        "https://api.github.com/repos/anndreluizz/VertexERP/releases/latest": json.dumps(dados).encode(),
        "https://x/zip": zip_bytes,
        "https://x/sha": f"{sha}  VertexERP-2026.10.14.5.zip\n".encode(),
    }
    return lambda pedido, timeout=None: _resposta(arquivos[pedido.full_url])


def _zip_pacote():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as pacote:
        pacote.writestr("atualizar.ps1", "# script")
        pacote.writestr("versao.txt", "2026.10.14.5")
    return buffer.getvalue()


def test_baixa_confere_hash_e_extrai(atualizador, tmp_path):
    abrir = _release(_zip_pacote())
    release = atualizador.buscar_ultima_versao(abrir)
    assert release["versao"] == "2026.10.14.5"

    pasta = atualizador.preparar_pacote(str(tmp_path), release, abrir)

    assert open(os.path.join(pasta, "versao.txt")).read() == "2026.10.14.5"
    assert not list((tmp_path / "atualizacoes").glob("*.zip"))


def test_hash_errado_nao_extrai_nada(atualizador, tmp_path):
    abrir = _release(_zip_pacote(), sha="0" * 64)
    release = atualizador.buscar_ultima_versao(abrir)

    with pytest.raises(RuntimeError, match="corrompido"):
        atualizador.preparar_pacote(str(tmp_path), release, abrir)

    assert not (tmp_path / "atualizacoes" / "2026.10.14.5").exists()


def test_nao_da_loja_so_pergunta_de_novo_amanha(atualizador, tmp_path):
    release = {"versao": "2026.10.14.5", "url_zip": "", "url_sha256": "", "notas": ""}
    perguntas = []

    def perguntar(titulo, texto):
        perguntas.append(texto)
        return False

    def nao_pode_instalar(*args):
        raise AssertionError("instalou sem a loja aceitar")

    for _ in range(2):
        atualizador.verificar_uma_vez(
            str(tmp_path), perguntar, lambda *a: None,
            buscar=lambda: release, preparar=nao_pode_instalar, instalar=nao_pode_instalar,
        )

    assert len(perguntas) == 1
    assert (tmp_path / "atualizacao_adiada.txt").read_text() == date.today().isoformat()


def test_sim_da_loja_baixa_e_instala(atualizador, tmp_path):
    release = {"versao": "2026.10.14.5", "url_zip": "", "url_sha256": "", "notas": ""}
    chamadas = []

    disparou = atualizador.verificar_uma_vez(
        str(tmp_path), lambda *a: True, lambda *a: None,
        buscar=lambda: release,
        preparar=lambda base, rel: chamadas.append("preparar") or "pasta",
        instalar=lambda base, pasta: chamadas.append(("instalar", pasta)),
    )

    assert disparou
    assert chamadas == ["preparar", ("instalar", "pasta")]


def test_ja_atualizado_nem_pergunta(atualizador, tmp_path):
    (tmp_path / "versao.txt").write_text("2026.10.14.5")
    release = {"versao": "2026.10.14.5", "url_zip": "", "url_sha256": "", "notas": ""}

    def perguntar(*args):
        raise AssertionError("perguntou sem ter versao nova")

    assert not atualizador.verificar_uma_vez(
        str(tmp_path), perguntar, lambda *a: None, buscar=lambda: release,
    )


def test_sem_internet_nao_incomoda(atualizador, tmp_path):
    def buscar():
        raise OSError("sem rede")

    def perguntar(*args):
        raise AssertionError("perguntou sem conseguir consultar")

    assert not atualizador.verificar_uma_vez(
        str(tmp_path), perguntar, lambda *a: None, buscar=buscar,
    )
    assert "sem rede" in (tmp_path / "atualizacao_log.txt").read_text(encoding="utf-8")


def test_instalacao_roda_mesmo_o_atualizar_ps1(atualizador, tmp_path):
    """O launcher mandava 'instalar' e o powershell (DETACHED_PROCESS)
    saia sem rodar nada -- a loja nunca atualizava, sem erro nenhum."""
    marca = tmp_path / "rodou.txt"
    (tmp_path / "atualizar.ps1").write_text(
        'param([string]$Raiz)\nSet-Content -Path "$Raiz\\rodou.txt" -Value ok\n',
        encoding="utf-8",
    )

    atualizador.iniciar_instalacao(str(tmp_path), str(tmp_path))

    for _ in range(60):
        if marca.exists():
            break
        time.sleep(0.5)
    assert marca.exists()
