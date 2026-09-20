def test_criar_conta_raiz(client, auth_headers):
    response = client.post(
        "/planos-conta/",
        json={"nome": "Despesas Operacionais", "tipo": "DESPESA"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = response.json()
    assert dados["nome"] == "Despesas Operacionais"
    assert dados["conta_pai_id"] is None


def test_criar_com_tipo_invalido_falha(client, auth_headers):
    response = client.post(
        "/planos-conta/",
        json={"nome": "X", "tipo": "LUCRO"},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_criar_subconta_herda_nome_do_pai(client, auth_headers):
    pai = client.post(
        "/planos-conta/",
        json={"nome": "Despesas", "tipo": "DESPESA"},
        headers=auth_headers,
    ).json()

    filha = client.post(
        "/planos-conta/",
        json={
            "nome": "Aluguel",
            "tipo": "DESPESA",
            "conta_pai_id": pai["id"],
        },
        headers=auth_headers,
    ).json()

    assert filha["conta_pai_id"] == pai["id"]
    assert filha["conta_pai_nome"] == "Despesas"


def test_subconta_com_tipo_diferente_do_pai_falha(client, auth_headers):
    pai = client.post(
        "/planos-conta/",
        json={"nome": "Receitas", "tipo": "RECEITA"},
        headers=auth_headers,
    ).json()

    response = client.post(
        "/planos-conta/",
        json={
            "nome": "Aluguel",
            "tipo": "DESPESA",
            "conta_pai_id": pai["id"],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_mover_conta_para_propria_subconta_falha(client, auth_headers):
    avo = client.post(
        "/planos-conta/",
        json={"nome": "Despesas", "tipo": "DESPESA"},
        headers=auth_headers,
    ).json()

    pai = client.post(
        "/planos-conta/",
        json={
            "nome": "Operacionais", "tipo": "DESPESA",
            "conta_pai_id": avo["id"],
        },
        headers=auth_headers,
    ).json()

    # tenta fazer o avo virar filho do proprio neto (pai) -- deve
    # detectar o ciclo e bloquear
    response = client.put(
        f"/planos-conta/{avo['id']}",
        json={
            "nome": "Despesas", "tipo": "DESPESA",
            "conta_pai_id": pai["id"], "ativo": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_excluir_conta_com_subconta_ativa_falha(client, auth_headers):
    pai = client.post(
        "/planos-conta/",
        json={"nome": "Despesas", "tipo": "DESPESA"},
        headers=auth_headers,
    ).json()

    client.post(
        "/planos-conta/",
        json={
            "nome": "Aluguel", "tipo": "DESPESA",
            "conta_pai_id": pai["id"],
        },
        headers=auth_headers,
    )

    response = client.delete(
        f"/planos-conta/{pai['id']}", headers=auth_headers
    )

    assert response.status_code == 400


def test_excluir_conta_some_da_listagem(client, auth_headers):
    conta = client.post(
        "/planos-conta/",
        json={"nome": "Descartável", "tipo": "DESPESA"},
        headers=auth_headers,
    ).json()

    response = client.delete(
        f"/planos-conta/{conta['id']}", headers=auth_headers
    )
    assert response.status_code == 200

    listagem = client.get("/planos-conta/", headers=auth_headers).json()
    assert conta["id"] not in [c["id"] for c in listagem]


def test_conta_pagar_com_plano_conta(client, auth_headers):
    plano = client.post(
        "/planos-conta/",
        json={"nome": "Aluguel", "tipo": "DESPESA"},
        headers=auth_headers,
    ).json()

    response = client.post(
        "/contas-pagar/",
        json={
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": "1500.00",
            "descricao": "Aluguel loja",
            "plano_conta_id": plano["id"],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = response.json()
    assert dados["plano_conta_id"] == plano["id"]
    assert dados["plano_conta_nome"] == "Aluguel"
