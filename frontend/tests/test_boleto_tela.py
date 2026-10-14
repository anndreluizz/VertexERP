"""Nova despesa lendo o boleto (código e PDF), aviso de boleto já
lançado, datas das parcelas ajustáveis, prazo da conta fixa e a janela
de parcelamento."""
from unittest import mock

import pytest
from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from telas import cadastro_despesa
from telas.cadastro_despesa import CadastroDespesaDialog
from telas.parcelamento import ParcelamentoDialog


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
    def __init__(self, status_code=200, corpo=None):
        self.status_code = status_code
        self._corpo = corpo or {}
        self.text = str(self._corpo)

    def json(self):
        return self._corpo


_LIDO = {
    "tipo": "BANCARIO",
    "linha_digitavel": "23791.23405 90000.001231 45009.876504 7 16360000132070",
    "codigo_barras": "23797163600001320701234090000001234500987650",
    "banco_nome": "Bradesco",
    "valor": "1320.70",
    "vencimento": "2026-11-20",
    "fornecedor_sugerido": "ADRIANA",
    "categoria_sugerida": "Calçados",
    "beneficiario_cnpj": "12345678000199",
    "ja_lancado": None,
}


def _dialogo(**kw):
    with mock.patch.object(cadastro_despesa, "rodar_em_thread"):
        dialogo = CadastroDespesaDialog(**kw)
    # categoria agora e obrigatoria (comeca vazia)
    dialogo._ao_carregar_categorias_sucesso([{"nome": "Fornecedores"}])
    dialogo.categoria.setCurrentIndex(0)
    return dialogo


def test_boleto_lido_preenche_a_despesa(_qapp):
    dialogo = _dialogo()

    dialogo._aplicar_boleto(dict(_LIDO))

    assert dialogo.valor.text() == "1320,70"
    assert dialogo.vencimento.date() == QDate(2026, 11, 20)
    assert dialogo.descricao.text() == "ADRIANA"
    assert dialogo.numero_boleto.text() == _LIDO["linha_digitavel"]
    assert "Bradesco" in dialogo.lbl_boleto.text()
    assert dialogo._categoria_selecionada_pendente == "Calçados"


def test_nao_troca_descricao_ja_digitada(_qapp):
    dialogo = _dialogo()
    dialogo.descricao.setText("ADRIANA CALÇADOS")

    dialogo._aplicar_boleto(dict(_LIDO))

    assert dialogo.descricao.text() == "ADRIANA CALÇADOS"


def test_boleto_repetido_mostra_aviso(_qapp):
    dialogo = _dialogo()
    lido = dict(_LIDO, ja_lancado={"id": 9, "descricao": "ADRIANA 1/3", "status": "PENDENTE", "valor": "1320.70"})

    dialogo._aplicar_boleto(lido)

    assert "já foi lançado" in dialogo.lbl_boleto.text()
    assert "ADRIANA 1/3" in dialogo.lbl_boleto.text()


def test_editando_so_mostra_o_boleto_sem_trocar_valores(_qapp):
    conta = {"id": 1, "descricao": "Luz", "valor": 99, "data_vencimento": "2026-10-20T00:00:00"}
    dialogo = _dialogo(conta=conta)

    dialogo._aplicar_boleto(dict(_LIDO))

    assert dialogo.valor.text() == "99,00"
    assert dialogo.descricao.text() == "Luz"


def test_bipar_o_codigo_dispara_a_leitura(_qapp, esperar_threads):
    dialogo = _dialogo()

    with mock.patch.object(
        cadastro_despesa, "ler_boleto", return_value=_Resposta(200, dict(_LIDO))
    ) as ler:
        dialogo.numero_boleto.setText(_LIDO["linha_digitavel"])
        dialogo._ler_codigo_digitado()  # o timer chamaria isso
        esperar_threads(dialogo)

    assert ler.call_args.kwargs["codigo"].startswith("2379")
    assert dialogo.valor.text() == "1320,70"


def test_codigo_invalido_mostra_erro(_qapp, esperar_threads):
    dialogo = _dialogo()

    with mock.patch.object(
        cadastro_despesa, "ler_boleto",
        return_value=_Resposta(400, {"detail": "O código do boleto tem um número errado."}),
    ):
        dialogo.numero_boleto.setText("2" * 47)
        dialogo._ler_codigo_digitado()
        esperar_threads(dialogo)

    assert "número errado" in dialogo.lbl_boleto.text()


def test_salvar_manda_o_cnpj_lido_do_pdf(_qapp, esperar_threads):
    dialogo = _dialogo()
    dialogo._aplicar_boleto(dict(_LIDO))

    with mock.patch.object(cadastro_despesa, "cadastrar_conta_pagar", return_value=_Resposta()) as cadastrar:
        dialogo.salvar()
        esperar_threads(dialogo)

    [dados] = cadastrar.call_args.args
    assert dados["beneficiario_cnpj"] == "12345678000199"
    assert dados["valor"] == 1320.70


def test_parcelas_a_cada_30_dias_e_datas_ajustadas(_qapp, esperar_threads):
    dialogo = _dialogo()
    dialogo.descricao.setText("NATURA")
    dialogo.valor.setText("1084,84")
    dialogo.vencimento.setDate(QDate(2026, 10, 5))
    dialogo.repeticao.setCurrentIndex(dialogo.repeticao.findData("PARCELADO"))
    dialogo.parcelas.setValue(3)
    dialogo.intervalo.setCurrentIndex(dialogo.intervalo.findData("30_DIAS"))

    assert "05/10, 04/11, 04/12" in dialogo.lbl_repeticao.text()

    dialogo._alternar_datas_parcelas()
    assert len(dialogo.datas_parcelas) == 3
    dialogo.datas_parcelas[2].setDate(QDate(2026, 12, 10))
    assert "10/12" in dialogo.lbl_repeticao.text()

    with mock.patch.object(cadastro_despesa, "cadastrar_conta_parcelada", return_value=_Resposta()) as parcelar:
        dialogo.salvar()
        esperar_threads(dialogo)

    dados, n = parcelar.call_args.args
    assert n == 3
    assert dados["intervalo"] == "30_DIAS"
    assert dados["vencimentos"] == ["2026-10-05", "2026-11-04", "2026-12-10"]


def test_conta_fixa_com_prazo_manda_os_meses(_qapp, esperar_threads):
    dialogo = _dialogo()
    dialogo.descricao.setText("AFEAM")
    dialogo.valor.setText("2874,43")
    dialogo.vencimento.setDate(QDate(2026, 10, 26))
    dialogo.repeticao.setCurrentIndex(dialogo.repeticao.findData("MENSAL"))
    dialogo.prazo.setCurrentIndex(dialogo.prazo.findData("MESES"))
    dialogo.meses.setValue(24)

    assert "26/09/2028" in dialogo.lbl_repeticao.text()

    with mock.patch.object(cadastro_despesa, "cadastrar_conta_fixa", return_value=_Resposta()) as fixa:
        dialogo.salvar()
        esperar_threads(dialogo)

    assert fixa.call_args.args[0]["meses"] == 24


def test_janela_de_parcelamento(_qapp, esperar_threads):
    parcelas = [
        {"id": 1, "parcela_numero": 1, "parcela_total": 3, "valor": 100, "status": "PAGO",
         "data_vencimento": "2026-10-10T00:00:00"},
        {"id": 2, "parcela_numero": 2, "parcela_total": 3, "valor": 100, "status": "PENDENTE",
         "data_vencimento": "2026-11-10T00:00:00"},
        {"id": 3, "parcela_numero": 3, "parcela_total": 3, "valor": 100, "status": "PENDENTE",
         "data_vencimento": "2026-12-10T00:00:00"},
    ]
    with mock.patch("telas.parcelamento.listar_parcelamento", return_value=parcelas):
        dialogo = ParcelamentoDialog({"descricao": "ADRIANA 1/3", "parcelamento_id": "abc"})
        esperar_threads(dialogo)

    assert dialogo.card_pago.lbl_valor.text() == "R$ 100,00"
    assert dialogo.card_falta.lbl_valor.text() == "R$ 200,00"
    assert "1 de 3" in dialogo.lbl_resumo.text()

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
         mock.patch("telas.parcelamento.cancelar_parcelas_restantes", return_value=_Resposta()) as cancelar, \
         mock.patch("telas.parcelamento.listar_parcelamento", return_value=parcelas):
        dialogo.cancelar_restantes()
        esperar_threads(dialogo)

    cancelar.assert_called_once_with("abc")
    assert dialogo.alterou


def test_enter_do_leitor_le_o_boleto_e_nao_salva(_qapp):
    with mock.patch.object(cadastro_despesa, "rodar_em_thread") as rodar:
        dialogo = CadastroDespesaDialog()
        dialogo.show()
        dialogo.numero_boleto.setText(_LIDO["codigo_barras"])
        QTest.keyClick(dialogo.numero_boleto, Qt.Key_Return)

    assert rodar.call_args.kwargs["codigo"] == _LIDO["codigo_barras"]
    assert dialogo.isVisible()


def test_codigo_com_numeros_a_mais_ou_a_menos_avisa(_qapp):
    with mock.patch.object(cadastro_despesa, "rodar_em_thread") as rodar:
        dialogo = CadastroDespesaDialog()
        dialogo.numero_boleto.setText("2" * 43)
        QTest.keyClick(dialogo.numero_boleto, Qt.Key_Return)

    assert not any(c.kwargs.get("codigo") for c in rodar.call_args_list)
    assert "43 números" in dialogo.lbl_boleto.text()


_PARCELA_2 = {
    "id": 22, "descricao": "AFEAM 2/18", "parcela_numero": 2, "parcela_total": 18,
    "valor": "1320.70", "data_vencimento": "2026-11-26T00:00:00",
}


def test_boleto_de_parcela_guarda_o_codigo_nela(_qapp, esperar_threads):
    dialogo = _dialogo()
    lido = dict(_LIDO, parcela_sugerida=dict(_PARCELA_2))

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes) as pergunta, \
         mock.patch.object(cadastro_despesa, "atualizar_conta_pagar", return_value=_Resposta()) as atualizar, \
         mock.patch.object(cadastro_despesa, "cadastrar_conta_pagar") as cadastrar:
        dialogo._aplicar_boleto(lido)
        esperar_threads(dialogo)

    assert "parcela 2 de 18" in pergunta.call_args.args[2]
    assert "20/11/2026" in pergunta.call_args.args[2]  # vencimento muda pro do boleto
    atualizar.assert_called_once_with(22, {
        "numero_boleto": _LIDO["linha_digitavel"],
        "data_vencimento": "2026-11-20T00:00:00",
    })
    cadastrar.assert_not_called()
    assert dialogo.result() == QDialog.Accepted


def test_boleto_de_parcela_recusado_vira_despesa_normal(_qapp):
    dialogo = _dialogo()
    lido = dict(_LIDO, parcela_sugerida=dict(_PARCELA_2))

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.No), \
         mock.patch.object(cadastro_despesa, "atualizar_conta_pagar") as atualizar:
        dialogo._aplicar_boleto(lido)

    atualizar.assert_not_called()
    assert dialogo.valor.text() == "1320,70"
    assert dialogo.result() != QDialog.Accepted


def _parcelas_sem_codigo():
    return [
        {"id": 1, "parcela_numero": 1, "parcela_total": 2, "valor": "1320.70", "status": "PAGO",
         "data_vencimento": "2026-10-20T00:00:00", "numero_boleto": "2379 1234"},
        {"id": 2, "parcela_numero": 2, "parcela_total": 2, "valor": "1320.70", "status": "PENDENTE",
         "data_vencimento": "2026-11-26T00:00:00", "numero_boleto": None},
    ]


def test_parcelamento_mostra_copiar_e_bipar(_qapp, esperar_threads):
    from PySide6.QtWidgets import QPushButton

    with mock.patch("telas.parcelamento.listar_parcelamento", return_value=_parcelas_sem_codigo()):
        dialogo = ParcelamentoDialog({"descricao": "AFEAM 1/2", "parcelamento_id": "abc"})
        esperar_threads(dialogo)

    textos = [
        dialogo.tabela.cellWidget(linha, 4).findChild(QPushButton).text().strip()
        for linha in range(2)
    ]
    assert textos == ["Copiar", "Bipar código"]


def test_bipar_codigo_na_parcela(_qapp, esperar_threads):
    with mock.patch("telas.parcelamento.listar_parcelamento", return_value=_parcelas_sem_codigo()):
        dialogo = ParcelamentoDialog({"descricao": "AFEAM 1/2", "parcelamento_id": "abc"})
        esperar_threads(dialogo)

        with mock.patch("telas.parcelamento.pedir_texto", return_value=(_LIDO["codigo_barras"], True)), \
             mock.patch("telas.parcelamento.ler_boleto", return_value=_Resposta(200, dict(_LIDO))), \
             mock.patch("telas.parcelamento.atualizar_conta_pagar", return_value=_Resposta()) as atualizar:
            dialogo.bipar_codigo(dialogo.parcelas[1])
            esperar_threads(dialogo)

    atualizar.assert_called_once_with(2, {
        "numero_boleto": _LIDO["linha_digitavel"],
        "data_vencimento": "2026-11-20T00:00:00",
    })
    assert dialogo.alterou


def test_bipar_boleto_de_outro_valor_pergunta_antes(_qapp, esperar_threads):
    with mock.patch("telas.parcelamento.listar_parcelamento", return_value=_parcelas_sem_codigo()):
        dialogo = ParcelamentoDialog({"descricao": "AFEAM 1/2", "parcelamento_id": "abc"})
        esperar_threads(dialogo)

    with mock.patch("telas.parcelamento.pedir_texto", return_value=(_LIDO["codigo_barras"], True)), \
         mock.patch("telas.parcelamento.ler_boleto", return_value=_Resposta(200, dict(_LIDO, valor="999.00"))), \
         mock.patch.object(QMessageBox, "question", return_value=QMessageBox.No), \
         mock.patch("telas.parcelamento.atualizar_conta_pagar") as atualizar:
        dialogo.bipar_codigo(dialogo.parcelas[1])

    atualizar.assert_not_called()
