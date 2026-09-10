"""Testes dos botões de LGPD na ficha do cliente -- exportar dados
pessoais e remover dados pessoais (direito de acesso e ao
esquecimento). Ver telas/ficha_cliente.py e services/cliente_service.py."""
from unittest import mock

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from telas.ficha_cliente import FichaClienteDialog


class _RespostaFalsa:
    def __init__(self, status_code, corpo):
        self.status_code = status_code
        self._corpo = corpo
        self.text = str(corpo)

    def json(self):
        return self._corpo


DADOS_LGPD_EXEMPLO = {
    "cliente_id": 1,
    "nome": "Cliente Teste",
    "cpf_cnpj": "123.456.789-00",
    "movimentos_fiado": [],
    "vendas": [],
    "observacoes": [],
}


def _tela():
    tela = FichaClienteDialog.__new__(FichaClienteDialog)
    tela.cliente = {"id": 1, "nome": "Cliente Teste"}
    return tela


def test_exportar_chama_o_servico_e_salva_o_json():
    tela = _tela()

    with mock.patch(
        "services.cliente_service.exportar_dados_lgpd",
        return_value=_RespostaFalsa(200, DADOS_LGPD_EXEMPLO),
    ) as exportar_mock, mock.patch.object(
        QFileDialog, "getSaveFileName", return_value=("C:/fake/dados_lgpd.json", "")
    ), mock.patch("builtins.open", mock.mock_open()) as open_mock, mock.patch(
        "telas.ficha_cliente.json.dump"
    ) as dump_mock, mock.patch.object(QMessageBox, "information") as info_mock:

        tela.exportar_dados_lgpd_atual()

    assert exportar_mock.call_args[0][0] == 1
    assert open_mock.called
    assert dump_mock.call_args[0][0] == DADOS_LGPD_EXEMPLO
    assert info_mock.called


def test_exportar_cancelar_dialogo_de_salvar_nao_escreve_nada():
    tela = _tela()

    with mock.patch(
        "services.cliente_service.exportar_dados_lgpd",
        return_value=_RespostaFalsa(200, DADOS_LGPD_EXEMPLO),
    ), mock.patch.object(QFileDialog, "getSaveFileName", return_value=("", "")), \
         mock.patch("builtins.open", mock.mock_open()) as open_mock:

        tela.exportar_dados_lgpd_atual()

    assert not open_mock.called


def test_exportar_com_erro_mostra_mensagem_sem_abrir_dialogo_de_salvar():
    tela = _tela()

    with mock.patch(
        "services.cliente_service.exportar_dados_lgpd",
        return_value=_RespostaFalsa(403, {"detail": "Acesso negado."}),
    ), mock.patch.object(QMessageBox, "critical") as erro_mock, \
         mock.patch.object(QFileDialog, "getSaveFileName") as save_dialog_mock:

        tela.exportar_dados_lgpd_atual()

    assert erro_mock.called
    assert not save_dialog_mock.called


def test_remover_com_confirmacao_chama_o_servico_e_fecha_a_ficha():
    tela = _tela()

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
         mock.patch(
             "services.cliente_service.remover_dados_lgpd",
             return_value=_RespostaFalsa(
                 200, {"cliente_id": 1, "mensagem": "Dados pessoais removidos com sucesso."}
             ),
         ) as remover_mock, mock.patch.object(QMessageBox, "information") as info_mock, \
         mock.patch.object(FichaClienteDialog, "accept") as accept_mock:

        tela.remover_dados_lgpd_atual()

    assert remover_mock.call_args[0][0] == 1
    assert info_mock.called
    assert accept_mock.called


def test_remover_cancelar_confirmacao_nao_chama_a_api():
    tela = _tela()

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.No), \
         mock.patch("services.cliente_service.remover_dados_lgpd") as remover_mock:

        tela.remover_dados_lgpd_atual()

    assert not remover_mock.called


def test_remover_com_saldo_devedor_mostra_erro_sem_fechar_a_ficha():
    tela = _tela()

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
         mock.patch(
             "services.cliente_service.remover_dados_lgpd",
             return_value=_RespostaFalsa(400, {"detail": "saldo devedor de R$ 50.00"}),
         ), mock.patch.object(QMessageBox, "critical") as erro_mock, \
         mock.patch.object(FichaClienteDialog, "accept") as accept_mock:

        tela.remover_dados_lgpd_atual()

    assert erro_mock.called
    assert not accept_mock.called
