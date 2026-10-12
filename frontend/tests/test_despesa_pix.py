"""Campo Pix da Nova despesa: chave ou copia e cola."""
from unittest import mock

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

from telas import cadastro_despesa
from telas.cadastro_despesa import CadastroDespesaDialog
from tests.test_pix import COPIA_E_COLA


@pytest.fixture(autouse=True)
def _destruir_janelas_do_teste(_qapp):
    antes = set(QApplication.topLevelWidgets())
    yield
    for janela in QApplication.topLevelWidgets():
        if janela not in antes:
            janela.close()
            janela.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    _qapp.processEvents()


class _Resposta:
    status_code = 200
    text = "{}"

    def json(self):
        return {}


def _dialogo(**kw):
    with mock.patch.object(cadastro_despesa, "rodar_em_thread"):
        return CadastroDespesaDialog(**kw)


def test_copia_e_cola_preenche_valor_e_fornecedor_e_vai_no_salvar(_qapp, esperar_threads):
    dialogo = _dialogo()
    dialogo.pix.setText(COPIA_E_COLA)

    assert dialogo.valor.text() == "150,00"
    assert dialogo.descricao.text() == "FULANO DE TAL"
    assert "copia e cola" in dialogo.lbl_pix.text()

    with mock.patch.object(cadastro_despesa, "cadastrar_conta_pagar", return_value=_Resposta()) as cadastrar:
        dialogo.salvar()
        esperar_threads(dialogo)

    [dados] = cadastrar.call_args.args
    assert dados["pix"] == COPIA_E_COLA


def test_chave_mostra_o_tipo(_qapp):
    dialogo = _dialogo()
    dialogo.pix.setText("(97) 99902-3190")
    assert "Telefone" in dialogo.lbl_pix.text()


def test_duplicar_leva_a_chave_mas_nao_o_copia_e_cola(_qapp):
    conta = {"id": 1, "descricao": "MARIA", "valor": 10, "data_vencimento": "2026-10-20T00:00:00"}
    assert _dialogo(duplicar_de={**conta, "pix": "maria@email.com"}).pix.text() == "maria@email.com"
    assert _dialogo(duplicar_de={**conta, "pix": COPIA_E_COLA}).pix.text() == ""
