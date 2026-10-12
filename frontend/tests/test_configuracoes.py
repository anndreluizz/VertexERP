"""Testes da tela de Configurações -- por enquanto só a aba
"Hardware / Scanner" (informativa: leitor USB/Bluetooth já funciona
sem nenhuma configuração, ver telas/pdv.py e telas/cadastro_produto.py)."""
from unittest import mock

from telas.configuracoes import Configuracoes


def _tela_configuracoes():
    with mock.patch("telas.configuracoes.configuracoes", return_value={}):
        with mock.patch("telas.configuracoes.me", return_value={"nome": "Usuário Teste", "id": 1}):
            with mock.patch("services.preferencias_service.carregar", return_value={}):
                with mock.patch(
                    "services.impressora_termica_service.listar_impressoras_windows",
                    return_value=[],
                ):
                    with mock.patch(
                        "services.preferencias_service.carregar_impressora_termica",
                        return_value=None,
                    ):
                        return Configuracoes()


def test_botao_hardware_scanner_esta_habilitado():
    tela = _tela_configuracoes()
    assert tela.bt_hardware.isEnabled()


def test_clicar_em_hardware_abre_a_aba_certa():
    tela = _tela_configuracoes()
    tela._selecionar_aba(6)

    assert tela.paginas.currentIndex() == 6
    assert tela.bt_hardware.isChecked()


def test_lojas_desativada_some_do_combo_do_terminal_e_tem_botoes():
    tela = _tela_configuracoes()
    lojas = [
        {"id": 1, "nome": "Matriz", "ativa": True},
        {"id": 2, "nome": "Filial", "ativa": False},
    ]

    with mock.patch("services.preferencias_service.carregar_loja_id", return_value=None):
        tela._ao_carregar_lojas_sucesso(lojas)

    itens = [tela.combo_loja_terminal.itemText(i) for i in range(tela.combo_loja_terminal.count())]
    assert itens == ["(usar a loja do usuário)", "Matriz"]
    assert tela.lista_lojas.count() == 2

    with mock.patch("services.preferencias_service.carregar_loja_id", return_value=2):
        tela._ao_carregar_lojas_sucesso(lojas)

    assert tela.combo_loja_terminal.currentText() == "Filial (desativada)"


def test_listar_lojas_esconde_inativas_por_padrao():
    from services import loja_service

    resposta = mock.Mock(status_code=200)
    resposta.json.return_value = [{"id": 1, "ativa": True}, {"id": 2, "ativa": False}]
    with mock.patch("services.loja_service.get", return_value=resposta):
        assert [l["id"] for l in loja_service.listar_lojas()] == [1]
        assert len(loja_service.listar_lojas(True)) == 2
