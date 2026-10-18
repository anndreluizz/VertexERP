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


def test_caixa_do_vendedor_nao_busca_os_totais(monkeypatch):
    from telas import caixa as tela_caixa

    def resumo_proibido():
        raise AssertionError("vendedor nao pode pedir o resumo do caixa")

    monkeypatch.setattr(tela_caixa, "caixa_aberto", lambda: {"id": 7})
    monkeypatch.setattr(tela_caixa, "resumo_caixa", resumo_proibido)
    monkeypatch.setattr(tela_caixa, "listar_movimentos_caixa", lambda caixa_id: ["mov"])

    assert tela_caixa._buscar_dados_caixa(False) == ({"id": 7}, {}, ["mov"])


def test_tela_caixa_do_vendedor_esconde_saldo_e_conferencia(_qapp, monkeypatch):
    from telas.caixa import Caixa

    monkeypatch.setattr(api, "_INFO_USUARIO_CACHE", {"admin": False, "permissoes": []})
    monkeypatch.setattr(Caixa, "carregar", lambda self: None)
    tela = Caixa()

    assert tela._ve_totais is False
    assert tela.lbl_total_previsto.isHidden()
    assert tela.bt_caixas_anteriores.isHidden()
    assert not tela.bt_sangria.isHidden() and not tela.bt_suprimento.isHidden()
