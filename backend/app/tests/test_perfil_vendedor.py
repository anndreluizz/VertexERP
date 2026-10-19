"""Vendedor = usuario comum sem financeiro.ver: nao abre as telas
financeiras e so' ve as proprias vendas/caixa. Admin ou perfil com
financeiro.ver continua vendo tudo."""

from datetime import date, datetime

import pytest

from app.models.caixa import Caixa
from app.models.perfil import Perfil
from app.models.venda import Venda

HOJE = date.today().isoformat()

ROTAS_FINANCEIRAS = [
    "/contas-pagar/",
    "/contas-recorrentes/",
    f"/relatorios/vendas?data_fim={HOJE}",
    "/extrato-bancario/",
    "/compras/",
    "/caixa/entradas",
    "/caixa/historico",
]


def _venda(db, usuario_id, valor):
    db.add(Venda(
        valor_total=valor, desconto=0, forma_pagamento="DINHEIRO",
        status="FINALIZADA", data=datetime.now(), usuario_id=usuario_id,
    ))
    db.commit()


@pytest.mark.parametrize("rota", ROTAS_FINANCEIRAS)
def test_vendedor_nao_abre_telas_financeiras(client, auth_headers_comum, auth_headers, rota):
    assert client.get(rota, headers=auth_headers_comum).status_code == 403
    assert client.get(rota, headers=auth_headers).status_code == 200


def test_perfil_com_financeiro_ver_abre(client, db, usuario_comum, auth_headers_comum):
    perfil = Perfil(nome="Gerente", permissoes=["financeiro.ver"])
    db.add(perfil)
    db.commit()
    usuario_comum.perfil_id = perfil.id
    db.commit()

    assert client.get("/contas-pagar/", headers=auth_headers_comum).status_code == 200


def test_vendedor_ve_so_as_proprias_vendas(client, db, usuario, usuario_comum, auth_headers_comum, auth_headers):
    _venda(db, usuario.id, 100)
    _venda(db, usuario_comum.id, 30)

    minhas = client.get("/vendas/", headers=auth_headers_comum).json()
    assert [float(v["valor_total"]) for v in minhas] == [30]
    # nem pedindo a de outro usuario
    outro = client.get(f"/vendas/?usuario_id={usuario.id}", headers=auth_headers_comum).json()
    assert [float(v["valor_total"]) for v in outro] == [30]

    assert len(client.get("/vendas/", headers=auth_headers).json()) == 2

    resumo = client.get(
        f"/vendas/resumo-vendedores?data_inicio={HOJE}&data_fim={HOJE}",
        headers=auth_headers_comum,
    ).json()
    assert [r["usuario_id"] for r in resumo] == [usuario_comum.id]


def test_dashboard_do_vendedor_so_com_os_numeros_dele(client, db, usuario, usuario_comum, auth_headers_comum, auth_headers):
    _venda(db, usuario.id, 100)
    _venda(db, usuario_comum.id, 30)
    db.add_all([
        Caixa(saldo_inicial=50, saldo_final=50, status="ABERTO", usuario_id=usuario.id),
        Caixa(saldo_inicial=20, saldo_final=20, status="ABERTO", usuario_id=usuario_comum.id),
    ])
    db.commit()

    dele = client.get("/dashboard/", headers=auth_headers_comum).json()
    assert float(dele["vendas_hoje"]) == 30
    # nem o saldo da propria gaveta (so' abre e faz sangria/suprimento)
    assert float(dele["saldo_caixa"]) == 0
    assert float(dele["contas_pagar"]) == 0
    assert all(float(p["valor"]) == 0 for p in dele["serie_pagamentos_mensal"])

    loja = client.get("/dashboard/", headers=auth_headers).json()
    assert float(loja["vendas_hoje"]) == 130
    assert float(loja["saldo_caixa"]) == 70


def test_vendedor_abre_caixa_mas_nao_ve_totais(client, db, usuario_comum, auth_headers_comum):
    aberto = client.post("/caixa/abrir", json={"saldo_inicial": 50}, headers=auth_headers_comum)
    assert aberto.status_code == 200, aberto.json()
    sangria = client.post(
        "/movimentos-caixa/", json={"tipo": "SUPRIMENTO", "valor": 10, "descricao": "t"},
        headers=auth_headers_comum,
    )
    assert sangria.status_code == 200, sangria.json()

    assert float(client.get("/caixa/aberto", headers=auth_headers_comum).json()["saldo_final"]) == 0
    assert client.get("/caixa/resumo", headers=auth_headers_comum).status_code == 403
    caixa_id = aberto.json()["id"]
    assert client.get(f"/caixa/{caixa_id}/resumo", headers=auth_headers_comum).status_code == 404

    # com caixa.fechar precisa conferir: ve os totais
    perfil = Perfil(nome="Fecha caixa", permissoes=["caixa.fechar"])
    db.add(perfil)
    db.commit()
    usuario_comum.perfil_id = perfil.id
    db.commit()
    assert client.get("/caixa/resumo", headers=auth_headers_comum).status_code == 200


def test_admin_prende_usuario_na_filial(client, db, usuario_comum, auth_headers):
    from app.models.loja import Loja

    filial = Loja(nome="Filial", ativa=True)
    db.add(filial)
    db.commit()

    resposta = client.put(f"/users/{usuario_comum.id}", json={"loja_id": filial.id}, headers=auth_headers)
    assert resposta.status_code == 200, resposta.json()
    db.refresh(usuario_comum)
    assert usuario_comum.loja_id == filial.id

    assert client.put(f"/users/{usuario_comum.id}", json={"loja_id": 9999}, headers=auth_headers).status_code == 400


def test_vendedor_nao_ve_resumo_do_caixa_de_outro(client, db, caixa_aberto, auth_headers_comum, auth_headers):
    rota = f"/caixa/{caixa_aberto.id}/resumo"
    assert client.get(rota, headers=auth_headers_comum).status_code == 404
    assert client.get(rota, headers=auth_headers).status_code == 200


def test_vendedor_nao_abre_venda_de_outro_pelo_id(client, db, usuario, usuario_comum, auth_headers_comum, auth_headers):
    _venda(db, usuario.id, 100)
    _venda(db, usuario_comum.id, 30)
    da_loja, minha = [v.id for v in db.query(Venda).order_by(Venda.id)]

    for sufixo in ("", "/comprovante", "/comprovante-envios", "/devolucoes"):
        assert client.get(f"/vendas/{da_loja}{sufixo}", headers=auth_headers_comum).status_code == 404
        assert client.get(f"/vendas/{minha}{sufixo}", headers=auth_headers_comum).status_code == 200
        assert client.get(f"/vendas/{da_loja}{sufixo}", headers=auth_headers).status_code == 200
