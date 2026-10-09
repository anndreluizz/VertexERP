from telas import fornecedores as tela
from telas.fornecedores import Fornecedores, formatar_cnpj, formatar_margem

DADOS = [
    {"id": 1, "razao_social": "Zeta Ltda", "nome_fantasia": "Atacadão", "cnpj": "75015373000135",
     "telefone": "(11) 4004-1234", "cidade": "São Paulo", "ativo": True, "margem_padrao": "25"},
    {"id": 2, "razao_social": "Limpa Tudo Ltda", "nome_fantasia": None, "cnpj": "40596873000100",
     "telefone": None, "cidade": None, "ativo": False, "margem_padrao": "12.5"},
]


def test_formatadores():
    assert formatar_cnpj("75015373000135") == "75.015.373/0001-35"
    assert formatar_cnpj("123") == "123"
    assert formatar_margem("25") == "25%"
    assert formatar_margem("12.5") == "12,50%"


def test_filtro_status_e_busca(monkeypatch):
    monkeypatch.setattr(tela.api, "usuario_tem_permissao", lambda _p: True)
    w = Fornecedores()
    w._ao_carregar_sucesso(DADOS)

    # padrão: só ativos (excluir é soft-delete)
    assert [f["id"] for f in w.fornecedores_exibidos] == [1]
    assert w.botoes_status["INATIVOS"].text() == "Inativos  1"

    w.selecionar_status("TODOS")
    assert [f["id"] for f in w.fornecedores_exibidos] == [1, 2]  # Atacadão antes de Limpa

    w.pesquisa.setText("75.015.373/0001")  # CNPJ com pontuação acha pelos dígitos
    assert [f["id"] for f in w.fornecedores_exibidos] == [1]

    w.pesquisa.setText("nada disso")
    assert w.fornecedores_exibidos == [] and not w.lbl_vazio.isHidden()
