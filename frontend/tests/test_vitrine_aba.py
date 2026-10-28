"""Aba Vitrine: filtros e o liga/desliga parcial direto na tabela."""
from PySide6.QtCore import Qt

import telas.vitrine as modulo
from telas.vitrine import COL_DESTAQUE, COL_SITE, Vitrine, passa_filtro, pendencias

NO_SITE = {"id": 1, "codigo": "0001", "nome": "Perfume", "ativo": True, "preco_efetivo": "57.99",
           "vitrine_publicar": True, "vitrine_destaque": False, "tem_foto": True, "categoria": ""}
FORA = {"id": 2, "codigo": "0002", "nome": "Bolsa", "ativo": True, "preco_efetivo": "30",
        "vitrine_publicar": False, "vitrine_destaque": False, "tem_foto": False, "categoria": "Bolsas"}


def test_filtros_e_pendencias():
    assert pendencias(NO_SITE) == ["sem categoria"]
    assert passa_filtro(NO_SITE, "PENDENCIA")
    # fora do site nao conta como pendencia, mesmo sem foto
    assert not passa_filtro(FORA, "PENDENCIA")
    assert not passa_filtro(FORA, "SITE") and passa_filtro(FORA, "TODOS")
    assert passa_filtro(NO_SITE, "TODOS", "perf") and not passa_filtro(NO_SITE, "TODOS", "xyz")


def test_marcar_manda_so_campos_da_vitrine(_qapp, monkeypatch):
    chamadas = []
    monkeypatch.setattr(modulo, "rodar_em_thread", lambda _p, _f, pid, dados, **_k: chamadas.append((pid, dados)))
    tela = Vitrine()
    tela._ao_carregar([dict(NO_SITE), dict(FORA)])
    assert [p["id"] for p in tela.exibidos] == [1]  # abre em "No site"

    tela.tabela.item(0, COL_DESTAQUE).setCheckState(Qt.Checked)
    assert chamadas[-1] == (1, {"codigo": "0001", "nome": "Perfume", "vitrine_publicar": True, "vitrine_destaque": True})

    # tirar do site leva o destaque junto
    tela.exibidos[0]["vitrine_destaque"] = True
    tela.tabela.item(0, COL_SITE).setCheckState(Qt.Unchecked)
    assert chamadas[-1][1]["vitrine_publicar"] is False
    assert chamadas[-1][1]["vitrine_destaque"] is False
