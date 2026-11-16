from datetime import date, timedelta
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest


def _conta(**extra):
    base = {
        "id": 1, "descricao": "Energia", "categoria": "Energia", "valor": 100,
        "status": "PENDENTE", "data_vencimento": (date.today() - timedelta(days=2)).isoformat(),
        "data_emissao": date.today().isoformat(), "numero_boleto": "123",
    }
    return {**base, **extra}


def test_ficha_pagar_e_editar_escolhem_a_acao(_qapp):
    from telas.ficha_boleto import FichaBoleto

    with patch("services.api.usuario_tem_permissao", lambda *_: True):
        ficha = FichaBoleto(_conta())
        ficha.bt_pagar.click()
        assert ficha.acao == "pagar_despesa"

        ficha = FichaBoleto(_conta())
        ficha.bt_editar.click()
        assert ficha.acao == "editar_despesa"


def test_ficha_conta_paga_nao_tem_botao_pagar(_qapp):
    from telas.ficha_boleto import FichaBoleto

    with patch("services.api.usuario_tem_permissao", lambda *_: True):
        ficha = FichaBoleto(_conta(status="PAGO", data_pagamento=date.today().isoformat()))
        assert not hasattr(ficha, "bt_pagar")


def test_clicar_na_linha_abre_a_ficha_e_nao_a_edicao(_qapp):
    from telas.contas_pagar import DespesaLinha

    with patch("services.api.usuario_tem_permissao", lambda *_: True):
        linha = DespesaLinha(_conta())
        linha.show()
        fichas, edicoes = [], []
        linha.ficha_solicitada.connect(fichas.append)
        linha.editar_solicitado.connect(edicoes.append)
        QTest.mouseClick(linha, Qt.LeftButton, pos=QPoint(60, 10))
        assert len(fichas) == 1 and not edicoes
