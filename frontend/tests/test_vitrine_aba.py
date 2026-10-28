"""Aba Vitrine: filtros e o liga/desliga parcial direto na tabela."""
from PySide6.QtCore import Qt

import telas.vitrine as modulo
from telas.vitrine import COL_DESTAQUE, COL_SITE, Vitrine, alterar_varios, passa_filtro, pendencias

NO_SITE = {"id": 1, "codigo": "0001", "nome": "Perfume", "ativo": True, "preco_efetivo": "57.99",
           "vitrine_publicar": True, "vitrine_destaque": False, "tem_foto": True, "categoria": "", "estoque": 3}
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
    def falso(_parent, _func, pid, dados, ao_sucesso=None, ao_erro=None, **_k):
        # mesma regra do rodar_em_thread real: lambda roda fora da GUI thread
        assert hasattr(ao_sucesso, "__self__") and hasattr(ao_erro, "__self__")
        chamadas.append((pid, dados))
    monkeypatch.setattr(modulo, "rodar_em_thread", falso)
    tela = Vitrine()
    tela._ao_carregar([dict(NO_SITE), dict(FORA)])
    assert [p["id"] for p in tela.exibidos] == [1]  # abre em "No site"

    tela.tabela.item(0, COL_DESTAQUE).setCheckState(Qt.Checked)
    assert chamadas[-1] == (1, {"codigo": "0001", "nome": "Perfume", "vitrine_publicar": True, "vitrine_destaque": True})

    tela.tabela.setEnabled(True)  # resposta do servidor nao vem no teste
    # tirar do site leva o destaque junto
    tela.exibidos[0]["vitrine_destaque"] = True
    tela.tabela.item(0, COL_SITE).setCheckState(Qt.Unchecked)
    assert chamadas[-1][1]["vitrine_publicar"] is False
    assert chamadas[-1][1]["vitrine_destaque"] is False


def test_sem_estoque_vira_aviso():
    assert "sem estoque (aparece esgotado)" in pendencias(dict(NO_SITE, estoque=0))


def test_por_varios_no_site(_qapp, monkeypatch):
    lotes = []

    def falso(_parent, func, alvo, publicar, ao_sucesso=None, ao_erro=None, **_k):
        assert func is alterar_varios and hasattr(ao_sucesso, "__self__") and hasattr(ao_erro, "__self__")
        lotes.append(([p["id"] for p in alvo], publicar))
    monkeypatch.setattr(modulo, "rodar_em_thread", falso)

    tela = Vitrine()
    tela._ao_carregar([dict(NO_SITE), dict(FORA), dict(FORA, id=3, codigo="0003", nome="Caneca")])
    tela.selecionar_filtro("TODOS")
    tela.tabela.selectAll()
    assert tela.bt_por.isEnabled() and tela.bt_tirar.isEnabled()

    tela.por_selecionados()  # so' os que ainda nao estao no site
    assert lotes[-1] == ([2, 3], True)


def test_alterar_varios_tira_destaque_junto(monkeypatch):
    enviados = []

    class Resposta:
        status_code = 200
    monkeypatch.setattr(modulo, "atualizar_produto", lambda pid, dados: enviados.append(dados) or Resposta())
    assert alterar_varios([dict(NO_SITE, vitrine_destaque=True)], False) == []
    assert enviados[0]["vitrine_publicar"] is False and enviados[0]["vitrine_destaque"] is False


def test_marcar_com_mil_produtos_nao_trava(_qapp, monkeypatch):
    """Na loja (~1000 produtos) marcar um item travava o Vertex: refazer a
    tabela com colunas em ResizeToContents era O(n²)."""
    import time

    monkeypatch.setattr(modulo, "rodar_em_thread", lambda *a, **k: None)
    tela = Vitrine()
    tela._ao_carregar([dict(FORA, id=i, codigo=f"{i:04d}", nome=f"PRODUTO {i}") for i in range(1000)])
    tela.selecionar_filtro("TODOS")
    tela.tabela.item(5, COL_SITE).setCheckState(Qt.Checked)

    class Ok:
        status_code = 200
    inicio = time.perf_counter()
    tela._ao_salvar(Ok())
    assert time.perf_counter() - inicio < 3
    assert tela.exibidos[5]["vitrine_publicar"] is True
