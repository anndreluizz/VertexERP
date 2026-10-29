"""Com ~1000 produtos a tela Produtos criava ~5000 widgets de uma vez e o
Vertex da loja parava de responder (29/10). So' as linhas visiveis montam."""
from telas import produtos as tela
from telas.produtos import Produtos

from tests.test_produtos_busca import _produto


def test_so_monta_widgets_das_linhas_visiveis_e_rolar_monta_o_resto(monkeypatch):
    monkeypatch.setattr(tela.api, "usuario_tem_permissao", lambda _p: True)
    w = Produtos()
    w.resize(1200, 800)
    w.show()
    w._ao_carregar_sucesso(([_produto(i) for i in range(1000)], []))

    assert w.tabela.cellWidget(0, 8) is not None
    assert w.tabela.cellWidget(999, 8) is None
    assert w.tabela.item(999, 3).text() == w.produtos_exibidos[999]["nome"]  # o texto ja' esta' la' (busca, selecao)

    w.tabela.scrollToBottom()
    assert w.tabela.cellWidget(999, 8) is not None
    assert len(w._linhas_montadas) < 100
