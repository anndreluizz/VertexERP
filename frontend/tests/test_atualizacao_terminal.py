"""Atualizacao do terminal: so' roda num terminal empacotado (nunca no
PC-servidor, que tem o backend ao lado) e compara versao por numero."""
import sys

from services import atualizacao_terminal as at


def test_compara_versao_por_numero():
    assert at.eh_mais_nova("2026.10.15.11", "2026.10.15.5")
    assert at.eh_mais_nova("2026.10.15.5", "0")
    assert not at.eh_mais_nova("2026.10.15.5", "2026.10.15.5")
    assert not at.eh_mais_nova("2026.10.14.9", "2026.10.15.1")


def test_so_vale_em_terminal_empacotado(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert at.raiz_terminal() is None  # rodando do codigo-fonte

    exe = tmp_path / "VertexERP-Frontend" / "VertexERP-Frontend.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert at.raiz_terminal() == str(tmp_path)

    (tmp_path / "VertexERP-Backend").mkdir()  # PC-servidor: quem atualiza e' o launcher
    assert at.raiz_terminal() is None


def test_versao_local(tmp_path):
    assert at.versao_local(str(tmp_path)) == "0"
    (tmp_path / "versao.txt").write_text("2026.10.15.11\n", encoding="utf-8")
    assert at.versao_local(str(tmp_path)) == "2026.10.15.11"


def test_script_da_troca_nao_roda_dentro_da_pasta_trocada(tmp_path, monkeypatch):
    # com cwd herdado dentro de VertexERP-Frontend o Rename-Item falha ("em uso")
    chamada = {}
    monkeypatch.setattr(at, "raiz_terminal", lambda: str(tmp_path))
    monkeypatch.setattr(at.subprocess, "Popen", lambda *a, **kw: chamada.update(kw))
    at.iniciar_troca("trocar.ps1", "nova", "2026.10.19.28")
    assert chamada["cwd"] and not chamada["cwd"].startswith(str(tmp_path))
