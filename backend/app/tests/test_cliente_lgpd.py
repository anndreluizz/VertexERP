"""Testes do direito de acesso (exportar) e ao esquecimento (anonimizar)
da LGPD pra dados de cliente -- ver ClienteService.exportar_dados_lgpd/
anonimizar_dados_lgpd e os endpoints GET/DELETE /clientes/{id}/dados-lgpd."""
from decimal import Decimal

import pytest

from app.models.movimento_fiado import MovimentoFiado
from app.models.venda import Venda
from app.services.cliente_service import ClienteService
from app.services.cliente_observacao_service import ClienteObservacaoService
from app.schemas.cliente import ClienteObservacaoCreate


def _criar_movimento(db, cliente, usuario, tipo, valor):
    movimento = MovimentoFiado(
        cliente_id=cliente.id,
        usuario_id=usuario.id,
        tipo=tipo,
        valor=Decimal(str(valor)),
        descricao=f"{tipo} de teste",
    )
    db.add(movimento)
    db.commit()
    db.refresh(movimento)
    return movimento


def _criar_venda(db, cliente, usuario, valor):
    venda = Venda(
        cliente_id=cliente.id,
        usuario_id=usuario.id,
        valor_total=Decimal(str(valor)),
        forma_pagamento="AVISTA",
        status="FINALIZADA",
    )
    db.add(venda)
    db.commit()
    db.refresh(venda)
    return venda


# ==================================================
# ClienteService.exportar_dados_lgpd
# ==================================================


def test_exportar_dados_lgpd_traz_dados_cadastrais(db, cliente):
    dados = ClienteService.exportar_dados_lgpd(db, cliente.id)

    assert dados["cliente_id"] == cliente.id
    assert dados["nome"] == cliente.nome
    assert dados["cpf_cnpj"] == cliente.cpf_cnpj
    assert dados["email"] == cliente.email
    assert dados["telefone"] == cliente.telefone


def test_exportar_dados_lgpd_traz_historico_completo(db, cliente, usuario):
    _criar_movimento(db, cliente, usuario, "COMPRA", 50)
    _criar_venda(db, cliente, usuario, 50)
    ClienteObservacaoService.criar(
        db, cliente.id, ClienteObservacaoCreate(texto="Observação de teste"), usuario.id,
    )

    dados = ClienteService.exportar_dados_lgpd(db, cliente.id)

    assert len(dados["movimentos_fiado"]) == 1
    assert len(dados["vendas"]) == 1
    assert len(dados["observacoes"]) == 1
    assert dados["saldo_devedor_fiado"] == Decimal("50.00")
    assert dados["observacoes"][0].texto == "Observação de teste"


def test_exportar_dados_lgpd_cliente_inexistente_da_erro(db):
    with pytest.raises(Exception, match="não encontrado"):
        ClienteService.exportar_dados_lgpd(db, 999999)


# ==================================================
# ClienteService.anonimizar_dados_lgpd
# ==================================================


def test_anonimizar_apaga_dados_pessoais_mas_mantem_historico(db, cliente, usuario):
    _criar_movimento(db, cliente, usuario, "COMPRA", 30)
    _criar_venda(db, cliente, usuario, 30)
    ClienteObservacaoService.criar(
        db, cliente.id, ClienteObservacaoCreate(texto="Nota sensível"), usuario.id,
    )

    # zera o saldo antes (nao pode anonimizar com divida em aberto --
    # ver teste especifico abaixo)
    _criar_movimento(db, cliente, usuario, "PAGAMENTO", 30)

    resultado = ClienteService.anonimizar_dados_lgpd(db, cliente.id)

    assert resultado["cliente_id"] == cliente.id

    db.refresh(cliente)

    assert cliente.nome == "Cliente removido (LGPD)"
    assert cliente.cpf_cnpj is None
    assert cliente.telefone is None
    assert cliente.email is None
    assert cliente.endereco is None
    assert cliente.data_nascimento is None
    assert cliente.foto is None
    assert cliente.ativo is False

    # historico contabil continua intacto
    assert len(cliente.vendas) == 1
    assert len(cliente.movimentos_fiado) == 2

    # observacoes (notas pessoais) foram removidas
    assert len(cliente.observacoes) == 0


def test_anonimizar_recusa_com_saldo_devedor_em_aberto(db, cliente, usuario):
    _criar_movimento(db, cliente, usuario, "COMPRA", 100)

    with pytest.raises(Exception, match="saldo devedor"):
        ClienteService.anonimizar_dados_lgpd(db, cliente.id)

    db.refresh(cliente)
    # nada foi alterado -- a recusa aconteceu antes de mexer em qualquer campo
    assert cliente.nome != "Cliente removido (LGPD)"


def test_anonimizar_cliente_inexistente_da_erro(db):
    with pytest.raises(Exception, match="não encontrado"):
        ClienteService.anonimizar_dados_lgpd(db, 999999)


def test_anonimizar_sem_nenhum_movimento_funciona(db, cliente):
    # cliente sem historico nenhum -- saldo eh 0, deve deixar remover
    resultado = ClienteService.anonimizar_dados_lgpd(db, cliente.id)
    assert "removidos" in resultado["mensagem"]


# ==================================================
# Endpoints -- GET/DELETE /clientes/{id}/dados-lgpd
# ==================================================


def test_exportar_dados_lgpd_endpoint_admin_funciona(client, auth_headers, cliente):
    response = client.get(f"/clientes/{cliente.id}/dados-lgpd", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["cliente_id"] == cliente.id


def test_exportar_dados_lgpd_endpoint_nao_admin_e_recusado(client, auth_headers_comum, cliente):
    response = client.get(f"/clientes/{cliente.id}/dados-lgpd", headers=auth_headers_comum)

    assert response.status_code == 403


def test_remover_dados_lgpd_endpoint_admin_funciona(client, auth_headers, cliente):
    response = client.delete(f"/clientes/{cliente.id}/dados-lgpd", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["cliente_id"] == cliente.id


def test_remover_dados_lgpd_endpoint_nao_admin_e_recusado(client, auth_headers_comum, cliente):
    response = client.delete(f"/clientes/{cliente.id}/dados-lgpd", headers=auth_headers_comum)

    assert response.status_code == 403


def test_remover_dados_lgpd_endpoint_com_saldo_devolve_400(
    client, auth_headers, cliente, usuario, db,
):
    _criar_movimento(db, cliente, usuario, "COMPRA", 20)

    response = client.delete(f"/clientes/{cliente.id}/dados-lgpd", headers=auth_headers)

    assert response.status_code == 400
    assert "saldo devedor" in response.json()["detail"]
