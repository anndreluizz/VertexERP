"""Terminal atualiza pela rede da loja: versao do servidor + zip do
frontend dele, montado uma vez por versao, com sha256."""

import hashlib
import io
import zipfile


def _instalacao(tmp_path, monkeypatch, versao="2026.10.15.11"):
    (tmp_path / "versao.txt").write_text(versao, encoding="utf-8")
    front = tmp_path / "VertexERP-Frontend"
    (front / "_internal").mkdir(parents=True)
    (front / "VertexERP-Frontend.exe").write_bytes(b"exe")
    (front / "_internal" / "lib.dll").write_bytes(b"dll")
    monkeypatch.setenv("VERTEXERP_INSTALL_DIR", str(tmp_path))


def test_sem_instalacao_nao_oferece_nada(client, auth_headers, monkeypatch):
    monkeypatch.delenv("VERTEXERP_INSTALL_DIR", raising=False)
    assert client.get("/atualizacao/terminal", headers=auth_headers).json() == {"versao": None}
    assert client.get("/atualizacao/terminal/pacote", headers=auth_headers).status_code == 404


def test_versao_e_pacote_do_terminal(client, auth_headers, tmp_path, monkeypatch):
    _instalacao(tmp_path, monkeypatch)

    assert client.get("/atualizacao/terminal", headers=auth_headers).json() == {
        "versao": "2026.10.15.11"
    }
    r = client.get("/atualizacao/terminal/pacote", headers=auth_headers)

    assert r.status_code == 200
    assert r.headers["x-versao"] == "2026.10.15.11"
    assert r.headers["x-sha256"] == hashlib.sha256(r.content).hexdigest()
    nomes = set(zipfile.ZipFile(io.BytesIO(r.content)).namelist())
    assert "VertexERP-Frontend/VertexERP-Frontend.exe" in nomes
    assert "VertexERP-Frontend/_internal/lib.dll" in nomes
    # montado uma vez so' por versao
    assert (tmp_path / "atualizacoes" / "terminal_2026.10.15.11.zip").exists()


def test_precisa_estar_logado(client, tmp_path, monkeypatch):
    _instalacao(tmp_path, monkeypatch)
    assert client.get("/atualizacao/terminal").status_code in (401, 403)
