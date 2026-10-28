"""Importar NF-e: 'Boleto' tambem pede vencimento/parcelas (vira Contas
a Pagar) e a categoria dos produtos novos vem da lista."""
import telas.importar_nfe as modulo


def test_boleto_mostra_parcelas_e_categoria_carrega(_qapp, monkeypatch):
    def falso(_parent, _func, *a, ao_sucesso=None, **_k):
        assert hasattr(ao_sucesso, "__self__")  # regra do rodar_em_thread real
        if _func is modulo.listar_categorias:
            ao_sucesso([{"nome": "ROUPA", "ativo": True}, {"nome": "VELHA", "ativo": False}])
    monkeypatch.setattr(modulo, "rodar_em_thread", falso)

    tela = modulo.ImportarNFeDialog()
    assert [tela.categoria.itemText(i) for i in range(tela.categoria.count())] == ["", "ROUPA"]

    tela._escolher_forma("BOLETO")
    assert not tela.bloco_parcelas.isHidden() and not tela.bloco_vencimento.isHidden()
    tela._escolher_forma("PIX")
    assert tela.bloco_parcelas.isHidden()
