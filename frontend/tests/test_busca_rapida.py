"""Busca rapida (Ctrl K): acha tela, cliente e produto sem acento."""
from design.busca_rapida import BuscaRapida, buscar

TELAS = [("clientes", "Clientes"), ("contas_pagar", "Boletos"), ("caixa", "Caixa")]
CLIENTES = [
    {"id": 1, "nome": "Raimunda Silva", "telefone": "97981000000"},
    {"id": 2, "nome": "Maria Raimunda", "telefone": None},
    {"id": 3, "nome": "João Batista", "telefone": "97988887777"},
]
PRODUTOS = [
    {"id": 9, "nome": "Sabão Rainha 1kg", "codigo_barras": "789123", "preco_venda": 12.9, "estoque": 8},
    {"id": 8, "nome": "Sandália infantil", "codigo_barras": "000555", "preco_venda": 39.9, "estoque": 0},
]


def test_sem_acento_e_comeca_antes_de_contem():
    res = buscar("RAI", TELAS, CLIENTES, PRODUTOS)
    clientes = [r[1] for r in res if r[3] == "cliente"]
    assert clientes == ["Raimunda Silva", "Maria Raimunda"]
    assert [r[1] for r in res if r[3] == "produto"] == ["Sabão Rainha 1kg"]

    assert [r[1] for r in buscar("joao", TELAS, CLIENTES, PRODUTOS)] == ["João Batista"]


def test_acha_tela_e_codigo_de_barras_e_telefone():
    assert buscar("bol", TELAS, [], [])[0][3:] == ("tela", "contas_pagar")
    assert buscar("000555", TELAS, CLIENTES, PRODUTOS)[0][1] == "Sandália infantil"
    assert buscar("979888", TELAS, CLIENTES, PRODUTOS)[0][1] == "João Batista"


def test_vazio_nao_lista_nada_e_limite_por_tipo():
    assert buscar("  ", TELAS, CLIENTES, PRODUTOS) == []
    muitos = [{"nome": f"Ana {i}"} for i in range(20)]
    assert len(buscar("ana", [], muitos, [], limite=5)) == 5


def test_enter_abre_o_primeiro_resultado_escolhivel():
    dialogo = BuscaRapida(TELAS, CLIENTES, PRODUTOS)
    escolhas = []
    dialogo.escolhido.connect(lambda tipo, alvo: escolhas.append((tipo, alvo)))
    dialogo.campo.setText("raimunda s")
    dialogo._abrir_atual()
    assert escolhas == [("cliente", CLIENTES[0])]
