"""Nova despesa com Repetição (parcelado / todo mês), janela de Contas
fixas e as marcas na lista de Contas a Pagar."""
from datetime import date
from unittest import mock

import pytest
from PySide6.QtCore import QDate, QEvent
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from services import conta_pagar_service
from telas import cadastro_despesa
from telas.cadastro_despesa import CadastroDespesaDialog, _somar_meses
from telas.contas_fixas import ContasFixasDialog


@pytest.fixture(autouse=True)
def _destruir_janelas_do_teste(_qapp):
    """Fecha e destrói as janelas criadas pelo teste. Sem isso, os
    diálogos sem dono acumulados derrubam o processo do pytest no
    encerramento quando rodam junto com o resto da suíte (Qt offscreen)."""
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


def _dialogo():
    with mock.patch.object(cadastro_despesa, "rodar_em_thread"):
        dialogo = CadastroDespesaDialog()
    # categoria agora e obrigatoria (comeca vazia)
    dialogo._ao_carregar_categorias_sucesso([{"nome": "Fornecedores"}])
    dialogo.categoria.setCurrentIndex(0)
    return dialogo


def _salvar(dialogo, esperar_threads, **patches):
    alvo = {
        "cadastrar_conta_pagar": mock.MagicMock(return_value=_Resposta()),
        "cadastrar_conta_parcelada": mock.MagicMock(return_value=_Resposta()),
        "cadastrar_conta_fixa": mock.MagicMock(return_value=_Resposta()),
    }
    with mock.patch.multiple(cadastro_despesa, **alvo):
        dialogo.salvar()
        esperar_threads(dialogo)
    return alvo


def test_somar_meses_respeita_mes_curto():
    assert _somar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert _somar_meses(date(2026, 11, 10), 2) == date(2027, 1, 10)


def test_parcelado_mostra_resumo_e_chama_rota_de_parcelas(_qapp, esperar_threads):
    dialogo = _dialogo()
    dialogo.descricao.setText("ADRIANA")
    dialogo.valor.setText("1320,70")
    dialogo.vencimento.setDate(QDate(2026, 10, 31))
    dialogo.repeticao.setCurrentIndex(dialogo.repeticao.findData("PARCELADO"))
    dialogo.parcelas.setValue(3)

    texto = dialogo.lbl_repeticao.text()
    assert "3 contas de R$ 1.320,70" in texto
    assert "total R$ 3.962,10" in texto
    assert "31/10, 30/11, 31/12" in texto

    chamadas = _salvar(dialogo, esperar_threads)

    dados, n = chamadas["cadastrar_conta_parcelada"].call_args.args
    assert n == 3
    assert dados["valor"] == 1320.70
    assert dados["descricao"] == "ADRIANA"
    chamadas["cadastrar_conta_pagar"].assert_not_called()


def test_todo_mes_cria_conta_fixa_com_valor_variavel(_qapp, esperar_threads):
    dialogo = _dialogo()
    dialogo.descricao.setText("Conta de luz")
    dialogo.valor.setText("605,24")
    dialogo.vencimento.setDate(QDate(2026, 11, 20))
    dialogo.repeticao.setCurrentIndex(dialogo.repeticao.findData("MENSAL"))
    dialogo.valor_variavel.setChecked(True)

    assert "Vence todo dia 20" in dialogo.lbl_repeticao.text()
    assert "Confirmar valor" in dialogo.lbl_repeticao.text()

    chamadas = _salvar(dialogo, esperar_threads)

    [dados] = chamadas["cadastrar_conta_fixa"].call_args.args
    assert dados["primeiro_vencimento"] == "2026-11-20"
    assert dados["valor_variavel"] is True
    assert dados["valor"] == 605.24


def test_todo_mes_leva_boleto_e_documento(_qapp, esperar_threads):
    dialogo = _dialogo()
    dialogo.descricao.setText("Conta de luz")
    dialogo.valor.setText("605,24")
    dialogo.numero_boleto.setText("83620000006052400481202611200000000000000000")
    dialogo.documento_bytes = b"%PDF-1.4 fatura"
    dialogo.documento_nome_arquivo = "fatura.pdf"
    dialogo.documento_tipo_arquivo = "application/pdf"
    dialogo.repeticao.setCurrentIndex(dialogo.repeticao.findData("MENSAL"))

    chamadas = _salvar(dialogo, esperar_threads)

    [dados] = chamadas["cadastrar_conta_fixa"].call_args.args
    assert dados["numero_boleto"].startswith("8362")
    assert dados["documento_nome"] == "fatura.pdf"
    assert dados["documento_base64"]


def test_so_esta_vez_continua_igual(_qapp, esperar_threads):
    dialogo = _dialogo()
    dialogo.descricao.setText("Conserto")
    dialogo.valor.setText("80,00")

    assert dialogo.parcelas.isHidden()
    assert dialogo.valor_variavel.isHidden()

    chamadas = _salvar(dialogo, esperar_threads)

    chamadas["cadastrar_conta_pagar"].assert_called_once()


def test_editar_conta_nao_mostra_repeticao(_qapp):
    conta = {"id": 1, "descricao": "Luz", "valor": 10, "data_vencimento": "2026-10-20T00:00:00"}
    with mock.patch.object(cadastro_despesa, "rodar_em_thread"):
        dialogo = CadastroDespesaDialog(conta=conta)

    assert dialogo.bloco_repeticao.isHidden()
    assert dialogo._tipo_repeticao() == "UNICA"


def test_linha_mostra_mensal_e_confirmar_valor(_qapp):
    conta = {
        "id": 1, "descricao": "Luz", "valor": 650, "status": "PENDENTE",
        "data_vencimento": "2099-11-20T00:00:00", "recorrente_id": 4,
        "valor_a_confirmar": True,
    }
    # import aqui dentro: importar telas.contas_pagar no topo do modulo
    # derruba o processo do pytest no encerramento quando roda junto com
    # test_configuracoes_backup (problema antigo do Qt offscreen, existe
    # com os arquivos originais tambem)
    from telas.contas_pagar import DespesaLinha

    linha = DespesaLinha(conta)

    from PySide6.QtWidgets import QLabel
    rotulos = [l.text() for l in linha.findChildren(QLabel)]
    assert "Mensal" in rotulos
    assert "Confirmar valor" in rotulos


def test_lista_varre_todas_as_paginas():
    paginas = [[{"id": i} for i in range(500)], [{"id": 999}]]
    with mock.patch.object(
        conta_pagar_service, "get",
        side_effect=[_Resposta(200, p) for p in paginas],
    ) as get:
        contas = conta_pagar_service.listar_contas_pagar()

    assert len(contas) == 501
    assert "skip=500" in get.call_args_list[1].args[0]


def test_contas_fixas_mudar_valor_e_parar(_qapp, esperar_threads):
    fixas = [{"id": 4, "descricao": "Funcionária", "valor": 1400, "dia_vencimento": 5,
              "valor_variavel": False}]
    with mock.patch("telas.contas_fixas.listar_contas_fixas", return_value=fixas):
        dialogo = ContasFixasDialog()
        esperar_threads(dialogo)

        assert dialogo.tabela.rowCount() == 1
        assert dialogo.tabela.item(0, 3).text() == "Valor fixo"
        dialogo.tabela.selectRow(0)

        with mock.patch.object(QInputDialog, "getDouble", return_value=(1500.0, True)), \
             mock.patch("telas.contas_fixas.atualizar_conta_fixa", return_value=_Resposta()) as atualizar:
            dialogo.mudar_valor()
            esperar_threads(dialogo)
        assert atualizar.call_args.args == (4, {"valor": 1500.0})

        dialogo.tabela.selectRow(0)
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
             mock.patch("telas.contas_fixas.parar_conta_fixa", return_value=_Resposta()) as parar:
            dialogo.parar()
            esperar_threads(dialogo)
        parar.assert_called_once_with(4)


def test_linha_copia_so_os_numeros_do_boleto(_qapp):
    from PySide6.QtGui import QGuiApplication
    from telas.contas_pagar import DespesaLinha

    conta = {
        "id": 1, "descricao": "LANJERIE", "valor": 933, "status": "PENDENTE",
        "data_vencimento": "2099-11-20T00:00:00",
        "numero_boleto": "23793.38128 60000.000003 00000.000400 1 84340000093300",
    }
    linha = DespesaLinha(conta)
    linha.bt_copiar.click()

    assert QGuiApplication.clipboard().text() == (
        "23793381286000000000300000000400184340000093300"
    )


def test_linha_sem_boleto_nao_tem_botao_copiar(_qapp):
    from telas.contas_pagar import DespesaLinha

    linha = DespesaLinha({"id": 2, "descricao": "Luz", "valor": 10, "status": "PENDENTE",
                          "data_vencimento": "2099-11-20T00:00:00"})

    assert not hasattr(linha, "bt_copiar")
