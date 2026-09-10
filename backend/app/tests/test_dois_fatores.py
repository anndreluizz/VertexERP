"""Testes unitarios do modulo app.auth.dois_fatores -- a parte pura
(sem tocar em banco/e-mail), que fica isolada bem cedo antes de ir
pro fluxo de login completo em test_auth.py."""

from datetime import datetime, timedelta

import pytest

from app.auth import dois_fatores


@pytest.fixture(autouse=True)
def _limpar_pendentes():
    dois_fatores._pendentes.clear()
    yield
    dois_fatores._pendentes.clear()


def test_gerar_codigo_tem_6_digitos():
    for _ in range(50):
        codigo = dois_fatores.gerar_codigo()
        assert len(codigo) == 6
        assert codigo.isdigit()


def test_criar_pendente_e_verificar_com_codigo_certo_funciona():
    verificacao_id, codigo = dois_fatores.criar_pendente(usuario_id=42)

    usuario_id = dois_fatores.verificar(verificacao_id, codigo)

    assert usuario_id == 42


def test_verificar_com_codigo_errado_falha():
    verificacao_id, codigo = dois_fatores.criar_pendente(usuario_id=42)

    resultado = dois_fatores.verificar(verificacao_id, "000000" if codigo != "000000" else "111111")

    assert resultado is None


def test_codigo_so_vale_uma_vez():
    verificacao_id, codigo = dois_fatores.criar_pendente(usuario_id=42)

    primeira = dois_fatores.verificar(verificacao_id, codigo)
    segunda = dois_fatores.verificar(verificacao_id, codigo)

    assert primeira == 42
    assert segunda is None


def test_verificacao_id_inexistente_falha():
    resultado = dois_fatores.verificar("id-que-nao-existe", "123456")
    assert resultado is None


def test_codigo_expirado_falha():
    verificacao_id, codigo = dois_fatores.criar_pendente(usuario_id=42)

    # forca a expiracao manipulando o relogio guardado, igual o
    # padrao ja usado em test_rate_limit.py
    dois_fatores._pendentes[verificacao_id]["expira_em"] = (
        datetime.utcnow() - timedelta(seconds=1)
    )

    resultado = dois_fatores.verificar(verificacao_id, codigo)

    assert resultado is None


def test_esgota_tentativas_e_invalida():
    verificacao_id, codigo = dois_fatores.criar_pendente(usuario_id=42)
    errado = "000000" if codigo != "000000" else "111111"

    for _ in range(dois_fatores.MAX_TENTATIVAS):
        resultado = dois_fatores.verificar(verificacao_id, errado)
        assert resultado is None

    # mesmo com o codigo CERTO agora, a entrada ja foi descartada
    # depois de esgotar as tentativas
    resultado_final = dois_fatores.verificar(verificacao_id, codigo)
    assert resultado_final is None


def test_pendentes_de_usuarios_diferentes_nao_se_confundem():
    id1, codigo1 = dois_fatores.criar_pendente(usuario_id=1)
    id2, codigo2 = dois_fatores.criar_pendente(usuario_id=2)

    assert dois_fatores.verificar(id1, codigo2) is None
    assert dois_fatores.verificar(id2, codigo1) is None

    assert dois_fatores.verificar(id1, codigo1) == 1
    assert dois_fatores.verificar(id2, codigo2) == 2
