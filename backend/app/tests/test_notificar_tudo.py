"""Eventos que avisam os admins (central do desktop + push no celular):
sangria/suprimento, venda cancelada, devolução, cliente novo e despesa."""
from app.models.notificacao import Notificacao
from app.tests.test_devolucao import _devolver, _vender


def _titulos(db):
    return [n.titulo for n in db.query(Notificacao).order_by(Notificacao.id).all()]


def _corpo(db, titulo):
    return db.query(Notificacao).filter(Notificacao.titulo == titulo).first().corpo


def test_sangria_e_suprimento_avisam(client, auth_headers, caixa_aberto, db):
    client.post("/movimentos-caixa/", json={"tipo": "SANGRIA", "descricao": "Pagar frete", "valor": 30.0}, headers=auth_headers)
    client.post("/movimentos-caixa/", json={"tipo": "SUPRIMENTO", "valor": 50.0}, headers=auth_headers)

    assert "Sangria no caixa" in _titulos(db)
    assert "Suprimento no caixa" in _titulos(db)
    assert _corpo(db, "Sangria no caixa") == "Usuário tirou R$ 30,00 do caixa: Pagar frete"


def test_venda_cancelada_avisa(client, auth_headers, produto, caixa_aberto, db):
    venda = _vender(client, auth_headers, produto, quantidade=1)

    response = client.delete(f"/vendas/{venda['id']}?motivo=Cliente desistiu", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert "Cliente desistiu" in _corpo(db, "Venda cancelada")


def test_devolucao_avisa(client, auth_headers, produto, caixa_aberto, db):
    venda = _vender(client, auth_headers, produto, quantidade=3)

    _devolver(client, auth_headers, venda, 1)

    assert "Tamanho errado" in _corpo(db, "Devolução na venda")


def test_cliente_novo_avisa(client, auth_headers, db):
    client.post("/clientes/", json={"nome": "MARIA TESTE"}, headers=auth_headers)

    assert _corpo(db, "Novo cliente") == "MARIA TESTE foi cadastrado."


def test_despesa_sem_boleto_avisa_os_outros_admins(client, auth_headers, usuario, db):
    from app.auth.hash import gerar_hash
    from app.models.user import User

    outro = User(nome="Dona", email="dona@vertex.com", senha=gerar_hash("123456"), ativo=True, admin=True)
    db.add(outro)
    db.commit()

    client.post(
        "/contas-pagar/",
        json={"descricao": "Frete", "valor": "80.00", "data_vencimento": "2026-11-10T00:00:00"},
        headers=auth_headers,
    )

    avisos = db.query(Notificacao).filter(Notificacao.titulo == "Nova despesa").all()
    # quem lançou não recebe aviso do que acabou de fazer
    assert [a.usuario_id for a in avisos] == [outro.id]
