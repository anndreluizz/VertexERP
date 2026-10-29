"""Busca de clientes (tela Clientes e F2 do PDV): nao remonta as linhas
a cada letra (eram ~2,5 s por letra com 400 clientes)."""
from telas import clientes as tela
from telas.clientes import Clientes
from telas.selecionar_cliente import MAX_RESULTADOS, SelecionarClienteDialog, _sem_acento


def _clientes(n):
    return [{"id": i, "nome": f"CLIENTE {i}", "telefone": f"9799{i:05d}",
             "ativo": True, "negativado": False} for i in range(n)]


def test_tela_clientes_busca_reaproveita_as_linhas(monkeypatch):
    w = Clientes()
    w._ao_carregar_sucesso((_clientes(40), {}, 0.0, {}))
    montadas = []
    original = tela.ClienteLinha
    monkeypatch.setattr(tela, "ClienteLinha", lambda *a: montadas.append(1) or original(*a))

    for letra in "cliente 1":
        w.pesquisa.insert(letra)
    visiveis = {cid for cid, linha in w._linhas.items() if not linha.isHidden()}
    assert visiveis == {c["id"] for c in w._clientes_filtrados}
    assert len(visiveis) == 11  # 1, 10..19

    w.pesquisa.clear()
    assert sum(not linha.isHidden() for linha in w._linhas.values()) == 40
    assert montadas == []


def test_f2_mostra_so_os_primeiros(monkeypatch):
    from telas import selecionar_cliente
    monkeypatch.setattr(selecionar_cliente, "rodar_em_thread", lambda *a, **k: None)
    d = SelecionarClienteDialog()
    d._ao_carregar_sucesso([
        {**c, "_agr": {}, "_busca_texto": _sem_acento(c["nome"]), "_busca_digitos": c["telefone"]}
        for c in _clientes(100)
    ])
    assert d.lista.count() == MAX_RESULTADOS
    assert "DIGITE MAIS" in d.lbl_contador.text()

    d.busca.setText("cliente 99")
    assert d.lista.count() == 1
