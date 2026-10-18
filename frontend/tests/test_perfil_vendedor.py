"""Vendedor (comum sem financeiro.ver) nao ve as telas financeiras no
menu; admin ve tudo; perfil com financeiro.ver vira "Gerente"."""

from services import api
from telas.principal import ITENS_MENU, pode_abrir_tela


def _telas(monkeypatch, info):
    monkeypatch.setattr(api, "_INFO_USUARIO_CACHE", info)
    return {chave for chave, _, _ in ITENS_MENU if pode_abrir_tela(chave)}


def test_vendedor_ve_so_as_telas_do_dia_a_dia(monkeypatch):
    telas = _telas(monkeypatch, {"admin": False, "permissoes": []})

    assert telas == {"dashboard", "pdv", "vendas", "produtos", "clientes", "caixa"}


def test_admin_ve_tudo(monkeypatch):
    assert len(_telas(monkeypatch, {"admin": True})) == len(ITENS_MENU)


def test_gerente_ve_financeiro_mas_nao_configuracoes(monkeypatch):
    telas = _telas(monkeypatch, {"admin": False, "permissoes": ["financeiro.ver"]})

    assert {"contas_pagar", "relatorios", "visao_geral"} <= telas
    assert "config" not in telas


def test_cargo():
    assert api.cargo_usuario({"admin": True}) == "Administrador"
    assert api.cargo_usuario({"admin": False, "permissoes": []}) == "Vendedor"
    assert api.cargo_usuario(
        {"admin": False, "permissoes": ["financeiro.ver"], "perfil_nome": "Gerente Filial"}
    ) == "Gerente Filial"
