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
