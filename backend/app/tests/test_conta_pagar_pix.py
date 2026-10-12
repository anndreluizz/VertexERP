"""Pix nas contas a pagar: chave do fornecedor ou copia e cola."""
from datetime import date

from app.services.conta_recorrente_service import ContaRecorrenteService, somar_meses

COPIA_E_COLA = (
    "00020126580014br.gov.bcb.pix0136123e4567-e12b-12d1-a456-426655440000"
    "5204000053039865406150.005802BR5913FULANO DE TAL6008BRASILIA62070503***6304ABCD"
)


def _conta(client, auth_headers, **extra):
    corpo = {"descricao": "MARIA", "valor": "150.00", "data_vencimento": "2026-10-20T00:00:00"}
    corpo.update(extra)
    response = client.post("/contas-pagar/", json=corpo, headers=auth_headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_guarda_e_devolve_o_pix(client, auth_headers):
    conta = _conta(client, auth_headers, pix="maria@email.com")
    assert conta["pix"] == "maria@email.com"


def test_conta_nova_do_mesmo_fornecedor_lembra_a_chave(client, auth_headers):
    _conta(client, auth_headers, pix="12345678900")
    assert _conta(client, auth_headers)["pix"] == "12345678900"
    assert _conta(client, auth_headers, descricao="OUTRO")["pix"] is None


def test_copia_e_cola_nao_e_lembrado(client, auth_headers):
    _conta(client, auth_headers, pix=COPIA_E_COLA)
    assert _conta(client, auth_headers)["pix"] is None


def test_editar_troca_o_pix(client, auth_headers):
    conta = _conta(client, auth_headers, pix="chave-velha")
    response = client.put(
        f"/contas-pagar/{conta['id']}", json={"pix": "chave-nova"}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["pix"] == "chave-nova"


def test_parcelado_copia_e_cola_so_na_primeira(client, auth_headers):
    response = client.post(
        "/contas-pagar/parcelado",
        json={
            "descricao": "ADRIANA", "valor": "100.00",
            "data_vencimento": "2026-10-31T00:00:00", "numero_parcelas": 3,
            "pix": COPIA_E_COLA,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert [c["pix"] for c in response.json()] == [COPIA_E_COLA, None, None]


def test_parcelado_chave_em_todas_e_lembrada_depois(client, auth_headers):
    response = client.post(
        "/contas-pagar/parcelado",
        json={
            "descricao": "ADRIANA", "valor": "100.00",
            "data_vencimento": "2026-10-31T00:00:00", "numero_parcelas": 2,
            "pix": "adriana@loja.com",
        },
        headers=auth_headers,
    )
    assert [c["pix"] for c in response.json()] == ["adriana@loja.com"] * 2
    # "ADRIANA 1/2" e "ADRIANA" sao o mesmo fornecedor
    assert _conta(client, auth_headers, descricao="ADRIANA")["pix"] == "adriana@loja.com"


def test_conta_fixa_leva_a_chave_pros_proximos_meses(client, auth_headers, db):
    response = client.post(
        "/contas-recorrentes/",
        json={
            "descricao": "Funcionária", "valor": "1400.00",
            "primeiro_vencimento": date.today().replace(day=4).isoformat(),
            "pix": "(97) 99999-0000",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    proximo_mes = somar_meses(date.today().replace(day=1), 1)
    ContaRecorrenteService.gerar_pendentes(db, hoje=proximo_mes.replace(day=2))

    contas = client.get("/contas-pagar/", headers=auth_headers).json()
    assert [c["pix"] for c in contas] == ["(97) 99999-0000"] * 2
