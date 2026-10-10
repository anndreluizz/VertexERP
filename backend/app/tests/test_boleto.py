"""Leitura de boleto (código e PDF), memória do fornecedor, aviso de
boleto repetido, parcelas ligadas e conta fixa com prazo."""
import base64
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services import boleto_service as b

HOJE = date(2026, 10, 9)


def _boleto_bancario(banco="237", valor_centavos=132070, vencimento=date(2026, 11, 20),
                     campo_livre="1234090000001234500987650"):
    """Código de barras válido montado com os dígitos verificadores."""
    fator = 1000 + (vencimento - date(2025, 2, 22)).days
    sem_dv = f"{banco}9{fator:04d}{valor_centavos:010d}{campo_livre}"
    dv = b._mod11_bancario(sem_dv)
    return sem_dv[:4] + str(dv) + sem_dv[4:]


def _conta_luz(valor_centavos=60524, empresa="0048", vencimento="20261120"):
    """Conta de consumo (segmento 3 = energia), valor real, DV mod 10."""
    sem_dv = f"836{valor_centavos:011d}{empresa}{vencimento}" + "0" * 17
    sem_dv = sem_dv[:43]
    dv = b._mod10(sem_dv[:3] + sem_dv[3:])
    return sem_dv[:3] + str(dv) + sem_dv[3:]


def _pdf_com_texto(linhas):
    """PDF mínimo (uma página, Helvetica) com as linhas de texto."""
    corpo = "BT /F1 10 Tf 40 800 Td 14 TL " + " ".join(
        "(" + l.replace("(", r"\(").replace(")", r"\)") + ") '" for l in linhas
    ) + " ET"
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(corpo.encode('latin-1'))} >>\nstream\n{corpo}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    saida = b"%PDF-1.4\n"
    posicoes = []
    for i, obj in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    inicio_xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for pos in posicoes:
        saida += f"{pos:010d} 00000 n \n".encode()
    saida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
        f"startxref\n{inicio_xref}\n%%EOF"
    ).encode()
    return saida


# ==================================================
# código
# ==================================================


def test_le_codigo_de_barras_e_linha_digitavel_do_mesmo_boleto():
    barras = _boleto_bancario()

    pelo_codigo = b.ler_codigo(barras, HOJE)
    pela_linha = b.ler_codigo(pelo_codigo["linha_digitavel"], HOJE)

    for lido in (pelo_codigo, pela_linha):
        assert lido["banco_nome"] == "Bradesco"
        assert lido["valor"] == Decimal("1320.70")
        assert lido["vencimento"] == date(2026, 11, 20)
        assert lido["chave_beneficiario"] == "237:12340098765"


def test_aceita_pontos_e_espacos():
    linha = b.ler_codigo(_boleto_bancario(), HOJE)["linha_digitavel"]
    assert " " in linha and "." in linha
    assert b.ler_codigo(linha.replace(" ", "  "), HOJE)["valor"] == Decimal("1320.70")


def test_numero_errado_e_recusado():
    linha = b._so_digitos(b.ler_codigo(_boleto_bancario(), HOJE)["linha_digitavel"])
    errada = linha[:12] + ("1" if linha[12] != "1" else "2") + linha[13:]

    with pytest.raises(b.BoletoInvalidoError):
        b.ler_codigo(errada, HOJE)


def test_codigo_incompleto_e_recusado():
    with pytest.raises(b.BoletoInvalidoError, match="incompleto"):
        b.ler_codigo("00199163600000605240", HOJE)


def test_fator_antigo_e_fator_novo():
    # fator 1000 = 03/07/2000 no ciclo antigo e 22/02/2025 no novo
    assert b.vencimento_pelo_fator("1000", HOJE) == date(2025, 2, 22)
    assert b.vencimento_pelo_fator("1000", date(2000, 7, 1)) == date(2000, 7, 3)
    assert b.vencimento_pelo_fator("0000", HOJE) is None


def test_conta_de_luz_sugere_energia():
    lido = b.ler_codigo(_conta_luz(), HOJE)

    assert lido["tipo"] == "ARRECADACAO"
    assert lido["valor"] == Decimal("605.24")
    assert lido["categoria_sugerida"] == "Energia"
    assert lido["vencimento"] == date(2026, 11, 20)
    # a linha de 48 dígitos volta pro mesmo código
    assert b.ler_codigo(lido["linha_digitavel"], HOJE)["codigo_barras"] == lido["codigo_barras"]


def test_chave_do_beneficiario_ignora_o_nosso_numero():
    um = b.ler_codigo(_boleto_bancario(campo_livre="1234090000001111100987650"), HOJE)
    outro = b.ler_codigo(_boleto_bancario(campo_livre="1234090000002222200987650"), HOJE)

    assert um["chave_beneficiario"] == outro["chave_beneficiario"]


# ==================================================
# PDF
# ==================================================


def test_le_pdf_com_codigo_e_beneficiario():
    linha = b.ler_codigo(_boleto_bancario(), HOJE)["linha_digitavel"]
    pdf = _pdf_com_texto([
        "Local de pagamento: Pagavel em qualquer banco",
        "Beneficiario: ADRIANA CALCADOS LTDA - CNPJ 12.345.678/0001-99",
        "Pagador: LOJA DO ANDRE",
        linha,
    ])

    lido = b.ler_pdf(pdf, HOJE)

    assert lido["valor"] == Decimal("1320.70")
    assert lido["beneficiario_nome"] == "ADRIANA CALCADOS LTDA"
    assert lido["beneficiario_cnpj"] == "12345678000199"


def test_beneficiario_na_linha_de_baixo():
    nome, cnpj = b.beneficiario_do_texto(
        "Beneficiário\nNATURA COSMETICOS S/A\nCNPJ: 71.673.990/0001-77\nAgência/Código"
    )
    assert nome == "NATURA COSMETICOS S/A"
    assert cnpj == "71673990000177"


def test_pdf_sem_codigo_e_sem_nome_da_erro_claro():
    with pytest.raises(b.BoletoInvalidoError, match="Não achei o código"):
        b.ler_pdf(_pdf_com_texto(["Recibo qualquer"]), HOJE)


# ==================================================
# API: ler, aprender, repetido
# ==================================================


def test_ler_boleto_aprende_o_fornecedor_e_avisa_repetido(client, auth_headers):
    barras = _boleto_bancario()

    primeira = client.post("/contas-pagar/ler-boleto", json={"codigo": barras}, headers=auth_headers).json()
    assert primeira["fornecedor_sugerido"] is None
    assert primeira["ja_lancado"] is None

    criada = client.post(
        "/contas-pagar/",
        json={
            "descricao": "ADRIANA", "valor": "1320.70", "categoria": "Calçados",
            "data_vencimento": "2026-11-20T00:00:00",
            "numero_boleto": primeira["linha_digitavel"],
        },
        headers=auth_headers,
    ).json()

    # outro boleto do mesmo beneficiário: nome e categoria já vêm
    outro = _boleto_bancario(campo_livre="1234090000009999900987650", valor_centavos=5000)
    segunda = client.post("/contas-pagar/ler-boleto", json={"codigo": outro}, headers=auth_headers).json()
    assert segunda["fornecedor_sugerido"] == "ADRIANA"
    assert segunda["categoria_sugerida"] == "Calçados"

    # o mesmo boleto de novo: avisa que já foi lançado
    repetido = client.post("/contas-pagar/ler-boleto", json={"codigo": barras}, headers=auth_headers).json()
    assert repetido["ja_lancado"]["id"] == criada["id"]


def test_ler_boleto_por_pdf_e_aprende_pelo_cnpj(client, auth_headers):
    pdf = _pdf_com_texto([
        "Beneficiario: ADRIANA CALCADOS LTDA - CNPJ 12.345.678/0001-99",
        b.ler_codigo(_boleto_bancario(), HOJE)["linha_digitavel"],
    ])
    lido = client.post(
        "/contas-pagar/ler-boleto",
        json={"pdf_base64": base64.b64encode(pdf).decode()},
        headers=auth_headers,
    ).json()
    assert lido["fornecedor_sugerido"] == "ADRIANA CALCADOS LTDA"

    client.post(
        "/contas-pagar/",
        json={"descricao": "ADRIANA", "valor": "10.00", "data_vencimento": "2026-11-20T00:00:00",
              "beneficiario_cnpj": lido["beneficiario_cnpj"]},
        headers=auth_headers,
    )

    de_novo = client.post(
        "/contas-pagar/ler-boleto",
        json={"pdf_base64": base64.b64encode(pdf).decode()},
        headers=auth_headers,
    ).json()
    assert de_novo["fornecedor_sugerido"] == "ADRIANA"


def test_ler_boleto_invalido_e_400(client, auth_headers):
    response = client.post("/contas-pagar/ler-boleto", json={"codigo": "123"}, headers=auth_headers)
    assert response.status_code == 400


# ==================================================
# parcelas ligadas
# ==================================================


def _parcelar(client, auth_headers, **extra):
    corpo = {
        "descricao": "ADRIANA", "valor": "1320.70",
        "data_vencimento": "2026-10-31T00:00:00", "numero_parcelas": 3,
    }
    corpo.update(extra)
    response = client.post("/contas-pagar/parcelado", json=corpo, headers=auth_headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_parcelas_ficam_ligadas(client, auth_headers):
    contas = _parcelar(client, auth_headers)

    ids = {c["parcelamento_id"] for c in contas}
    assert len(ids) == 1 and None not in ids
    assert [(c["parcela_numero"], c["parcela_total"]) for c in contas] == [(1, 3), (2, 3), (3, 3)]

    grupo = client.get(f"/contas-pagar/parcelamento/{contas[0]['parcelamento_id']}", headers=auth_headers).json()
    assert [c["id"] for c in grupo] == [c["id"] for c in contas]


def test_parcelas_a_cada_30_dias(client, auth_headers):
    contas = _parcelar(client, auth_headers, data_vencimento="2026-10-05T00:00:00", intervalo="30_DIAS")

    assert [c["data_vencimento"][:10] for c in contas] == ["2026-10-05", "2026-11-04", "2026-12-04"]


def test_parcelas_com_datas_escolhidas(client, auth_headers):
    contas = _parcelar(client, auth_headers, vencimentos=["2026-10-10", "2026-11-15", "2026-12-20"])

    assert [c["data_vencimento"][:10] for c in contas] == ["2026-10-10", "2026-11-15", "2026-12-20"]


def test_datas_escolhidas_precisam_bater_com_a_quantidade(client, auth_headers):
    response = client.post(
        "/contas-pagar/parcelado",
        json={"descricao": "X", "valor": "10.00", "data_vencimento": "2026-10-10T00:00:00",
              "numero_parcelas": 3, "vencimentos": ["2026-10-10"]},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_cancelar_parcelas_restantes_mantem_as_pagas(client, auth_headers):
    contas = _parcelar(client, auth_headers)
    client.post(f"/contas-pagar/{contas[0]['id']}/pagar", headers=auth_headers)

    response = client.post(
        f"/contas-pagar/parcelamento/{contas[0]['parcelamento_id']}/cancelar-restantes",
        headers=auth_headers,
    )

    assert response.json()["canceladas"] == 2
    grupo = client.get(f"/contas-pagar/parcelamento/{contas[0]['parcelamento_id']}", headers=auth_headers).json()
    assert [c["status"] for c in grupo] == ["PAGO", "CANCELADO", "CANCELADO"]


# ==================================================
# conta fixa com prazo (empréstimo)
# ==================================================


def test_conta_fixa_com_prazo_para_sozinha(client, auth_headers, db):
    from app.services.conta_recorrente_service import ContaRecorrenteService, somar_meses

    inicio = date.today().replace(day=10)
    fixa = client.post(
        "/contas-recorrentes/",
        json={"descricao": "AFEAM", "valor": "2874.43", "primeiro_vencimento": inicio.isoformat(),
              "meses": 3},
        headers=auth_headers,
    ).json()
    assert fixa["fim_competencia"] == somar_meses(inicio.replace(day=1), 2).isoformat()

    ContaRecorrenteService.gerar_pendentes(db, hoje=somar_meses(inicio.replace(day=1), 6))

    contas = client.get("/contas-pagar/", headers=auth_headers).json()
    assert len(contas) == 3
    # acabou o prazo: sai da lista de contas fixas
    assert client.get("/contas-recorrentes/", headers=auth_headers).json() == []


def test_boleto_de_parcela_acha_a_parcela_sem_codigo(client, auth_headers):
    contas = _parcelar(
        client, auth_headers, descricao="AFEAM",
        vencimentos=["2026-10-26", "2026-11-26", "2026-12-26"],
    )
    # o banco mandou o boleto da 2a com vencimento dia 24, nao 26
    barras = _boleto_bancario(vencimento=date(2026, 11, 24))

    lido = client.post("/contas-pagar/ler-boleto", json={"codigo": barras}, headers=auth_headers).json()

    sugerida = lido["parcela_sugerida"]
    assert sugerida["id"] == contas[1]["id"]
    assert (sugerida["parcela_numero"], sugerida["parcela_total"]) == (2, 3)

    # guardou o codigo nela: o mesmo boleto agora e' "ja lancado", nao sugestao
    client.put(
        f"/contas-pagar/{contas[1]['id']}",
        json={"numero_boleto": lido["linha_digitavel"], "data_vencimento": "2026-11-24T00:00:00"},
        headers=auth_headers,
    )
    de_novo = client.post("/contas-pagar/ler-boleto", json={"codigo": barras}, headers=auth_headers).json()
    assert de_novo["parcela_sugerida"] is None
    assert de_novo["ja_lancado"]["id"] == contas[1]["id"]


def test_boleto_de_outro_valor_nao_sugere_parcela(client, auth_headers):
    _parcelar(client, auth_headers, vencimentos=["2026-10-26", "2026-11-26", "2026-12-26"])
    barras = _boleto_bancario(valor_centavos=99900, vencimento=date(2026, 11, 26))

    lido = client.post("/contas-pagar/ler-boleto", json={"codigo": barras}, headers=auth_headers).json()

    assert lido["parcela_sugerida"] is None


def test_le_pdf_com_codigo_do_banco_antes_da_linha_digitavel():
    linha = b.ler_codigo(_boleto_bancario(), HOJE)["linha_digitavel"]
    pdf = _pdf_com_texto([
        "Beneficiario: ADRIANA CALCADOS LTDA",
        f"237-2 {linha}",
    ])

    lido = b.ler_pdf(pdf, HOJE)

    assert lido["valor"] == Decimal("1320.70")
    assert lido["vencimento"] == date(2026, 11, 20)
