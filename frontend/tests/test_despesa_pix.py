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
        dialogo = CadastroDespesaDialog(**kw)
    # categoria agora e obrigatoria (comeca vazia)
    dialogo._ao_carregar_categorias_sucesso([{"nome": "Fornecedores"}])
    dialogo.categoria.setCurrentIndex(0)
    return dialogo


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


def test_categoria_comeca_vazia_e_e_obrigatoria(_qapp):
    # antes vinha marcada a 1a categoria da lista e passava batido
    # (parcelas de fornecedor foram gravadas como "Energia")
    with mock.patch.object(cadastro_despesa, "rodar_em_thread"):
        dialogo = CadastroDespesaDialog()
    dialogo._ao_carregar_categorias_sucesso([{"nome": "Energia"}, {"nome": "roupas"}])
    assert dialogo.categoria.currentIndex() == -1

    dialogo.descricao.setText("FORNECEDOR")
    dialogo.valor.setText("100,00")
    with mock.patch.object(cadastro_despesa.QMessageBox, "warning") as aviso, \
            mock.patch.object(cadastro_despesa, "cadastrar_conta_pagar") as cadastrar:
        dialogo.salvar()
    assert "categoria" in aviso.call_args.args[2]
    cadastrar.assert_not_called()
