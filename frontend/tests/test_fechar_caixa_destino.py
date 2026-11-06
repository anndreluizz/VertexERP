"""Fechar Caixa: quanto vai pro cofre/banco e quanto os socios levam (o
resto fica de troco) -- nao pode tirar mais do que foi contado."""
from types import SimpleNamespace

from telas.fechar_caixa import FecharCaixaWindow


def _tela(contado, guardado, retirado):
    campo = lambda t: SimpleNamespace(text=lambda: t)
    return SimpleNamespace(valor_contado=contado, guardado_input=campo(guardado),
                           retirado_input=campo(retirado))


def test_destino_do_dinheiro():
    assert FecharCaixaWindow._destino(_tela(300, "200,00", "60")) == (200, 60, 40)
    assert FecharCaixaWindow._destino(_tela(300, "", "")) == (0, 0, 300)
    assert FecharCaixaWindow._destino(_tela(1500, "1.500,00", "0")) == (1500, 0, 0)
    assert FecharCaixaWindow._destino(_tela(300, "250", "60")) is None  # passa do contado
    assert FecharCaixaWindow._destino(_tela(300, "abc", "0")) is None
    assert FecharCaixaWindow._destino(_tela(300, "-5", "0")) is None


def test_contar_por_nota_soma_e_preenche():
    from telas.fechar_caixa import soma_notas
    assert soma_notas({100: 1, 50: 2, 20: 5, 10: 4, 5: 6, 2: 5, 200: 0}, 2.0) == 382.0
    assert soma_notas({}, 0) == 0
