"""Contas fixas mensais (luz, funcionária) e boleto parcelado."""
from datetime import date
from decimal import Decimal

from app.services.conta_recorrente_service import (
    ContaRecorrenteService,
    somar_meses,
    vencimento_no_mes,
)


def _fixa(client, auth_headers, **extra):
    corpo = {
        "descricao": "Funcionária",
        "valor": "1400.00",
        "primeiro_vencimento": date.today().replace(day=5).isoformat(),
        "valor_variavel": False,
        "categoria": "Salários",
    }
    corpo.update(extra)
    response = client.post("/contas-recorrentes/", json=corpo, headers=auth_headers)
    assert response.status_code == 200, response.text
    return response.json()


def _contas(client, auth_headers):
    return client.get("/contas-pagar/", headers=auth_headers).json()


# ==================================================
# datas
# ==================================================


def test_vencimento_em_mes_curto_cai_no_ultimo_dia():
    assert vencimento_no_mes(date(2026, 2, 1), 31) == date(2026, 2, 28)
    assert vencimento_no_mes(date(2026, 3, 1), 31) == date(2026, 3, 31)


def test_somar_meses_vira_o_ano():
    assert somar_meses(date(2026, 11, 1), 3) == date(2027, 2, 1)


# ==================================================
# conta fixa
# ==================================================


def test_criar_conta_fixa_ja_cria_a_conta_do_mes(client, auth_headers):
    fixa = _fixa(client, auth_headers)

    [conta] = _contas(client, auth_headers)

    assert conta["recorrente_id"] == fixa["id"]
    assert conta["descricao"] == "Funcionária"
    assert Decimal(str(conta["valor"])) == Decimal("1400.00")
    assert conta["valor_a_confirmar"] is False
    assert conta["data_vencimento"].startswith(date.today().replace(day=5).isoformat())


def test_listar_de_novo_no_mesmo_mes_nao_duplica(client, auth_headers):
    _fixa(client, auth_headers)

    _contas(client, auth_headers)
    _contas(client, auth_headers)

    assert len(_contas(client, auth_headers)) == 1


def test_virada_do_mes_cria_a_proxima_com_valor_fixo(client, auth_headers, db):
    fixa = _fixa(client, auth_headers)

    proximo_mes = somar_meses(date.today().replace(day=1), 1)
    criadas = ContaRecorrenteService.gerar_pendentes(db, hoje=proximo_mes.replace(day=2))

    assert criadas == 1
    contas = sorted(_contas(client, auth_headers), key=lambda c: c["data_vencimento"])
    assert len(contas) == 2
    assert contas[1]["data_vencimento"].startswith(proximo_mes.replace(day=5).isoformat())
    assert Decimal(str(contas[1]["valor"])) == Decimal("1400.00")
    assert contas[1]["valor_a_confirmar"] is False
    assert contas[1]["recorrente_id"] == fixa["id"]


def test_luz_nasce_com_valor_do_mes_anterior_a_confirmar(client, auth_headers, db):
    _fixa(
        client, auth_headers,
        descricao="Conta de luz", valor="605.24", valor_variavel=True,
        primeiro_vencimento=date.today().replace(day=20).isoformat(),
    )

    # a fatura deste mês veio diferente: corrige o valor
    [deste_mes] = _contas(client, auth_headers)
    client.put(
        f"/contas-pagar/{deste_mes['id']}", json={"valor": "650.00"}, headers=auth_headers
    )

    proximo_mes = somar_meses(date.today().replace(day=1), 1)
    ContaRecorrenteService.gerar_pendentes(db, hoje=proximo_mes)

    contas = sorted(_contas(client, auth_headers), key=lambda c: c["data_vencimento"])
    assert Decimal(str(contas[1]["valor"])) == Decimal("650.00")
    assert contas[1]["valor_a_confirmar"] is True

    # corrigir o valor confirma
    corrigida = client.put(
        f"/contas-pagar/{contas[1]['id']}", json={"valor": "590.10"}, headers=auth_headers
    ).json()
    assert corrigida["valor_a_confirmar"] is False


def test_pagar_tambem_confirma_o_valor(client, auth_headers, db):
    _fixa(client, auth_headers, descricao="Luz", valor="100.00", valor_variavel=True)
    ContaRecorrenteService.gerar_pendentes(
        db, hoje=somar_meses(date.today().replace(day=1), 1)
    )
    conta = [c for c in _contas(client, auth_headers) if c["valor_a_confirmar"]][0]

    paga = client.post(f"/contas-pagar/{conta['id']}/pagar", headers=auth_headers).json()

    assert paga["valor_a_confirmar"] is False


def test_parar_de_repetir_nao_cria_mais_meses(client, auth_headers, db):
    fixa = _fixa(client, auth_headers)

    assert client.delete(f"/contas-recorrentes/{fixa['id']}", headers=auth_headers).status_code == 200
    ContaRecorrenteService.gerar_pendentes(
        db, hoje=somar_meses(date.today().replace(day=1), 3)
    )

    assert len(_contas(client, auth_headers)) == 1
    assert client.get("/contas-recorrentes/", headers=auth_headers).json() == []


def test_editar_conta_fixa_muda_os_proximos_meses(client, auth_headers, db):
    fixa = _fixa(client, auth_headers)

    response = client.put(
        f"/contas-recorrentes/{fixa['id']}", json={"valor": "1500.00"}, headers=auth_headers
    )
    assert response.status_code == 200

    ContaRecorrenteService.gerar_pendentes(
        db, hoje=somar_meses(date.today().replace(day=1), 1)
    )
    valores = sorted(Decimal(str(c["valor"])) for c in _contas(client, auth_headers))
    assert valores == [Decimal("1400.00"), Decimal("1500.00")]


def test_primeiro_vencimento_no_passado_cria_os_meses_ate_hoje(client, auth_headers):
    dois_meses_atras = somar_meses(date.today().replace(day=1), -2).replace(day=10)

    _fixa(client, auth_headers, primeiro_vencimento=dois_meses_atras.isoformat())

    assert len(_contas(client, auth_headers)) == 3


# ==================================================
# parcelado
# ==================================================


def test_boleto_parcelado_cria_uma_conta_por_mes(client, auth_headers):
    response = client.post(
        "/contas-pagar/parcelado",
        json={
            "descricao": "ADRIANA",
            "valor": "1320.70",
            "data_vencimento": "2026-10-31T00:00:00",
            "numero_parcelas": 3,
            "categoria": "Calçados",
            "numero_boleto": "123",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    contas = response.json()
    assert [c["descricao"] for c in contas] == ["ADRIANA 1/3", "ADRIANA 2/3", "ADRIANA 3/3"]
    # dia 31: novembro tem 30 dias
    assert [c["data_vencimento"][:10] for c in contas] == [
        "2026-10-31", "2026-11-30", "2026-12-31",
    ]
    assert all(Decimal(str(c["valor"])) == Decimal("1320.70") for c in contas)
    assert [c["numero_boleto"] for c in contas] == ["123", None, None]


def test_parcelado_exige_pelo_menos_duas_parcelas(client, auth_headers):
    response = client.post(
        "/contas-pagar/parcelado",
        json={
            "descricao": "X", "valor": "10.00",
            "data_vencimento": "2026-10-31T00:00:00", "numero_parcelas": 1,
        },
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_aviso_diario_cria_o_mes_e_avisa_valor_a_confirmar(client, auth_headers, db, monkeypatch):
    from app.services import aviso_vencimento_service
    from app.services.notificacao_service import NotificacaoService

    _fixa(client, auth_headers, descricao="Luz", valor="100.00", valor_variavel=True)
    ContaRecorrenteService.gerar_pendentes(
        db, hoje=somar_meses(date.today().replace(day=1), 1)
    )

    avisos = []
    monkeypatch.setattr(
        NotificacaoService, "enviar_para_admins",
        lambda db, titulo, corpo, **kw: avisos.append(titulo),
    )

    aviso_vencimento_service.verificar_vencimentos_e_notificar(db)

    assert "Contas com valor a confirmar" in avisos
