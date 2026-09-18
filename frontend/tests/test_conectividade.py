"""Indicador de "sem conexão com o servidor" (ver design/header.py e
telas/principal.py) -- checagem leve em segundo plano pra avisar cedo
quando a rede cai no meio da sessão, sem travar nem bloquear nada."""
from unittest import mock

from services import api


class _RespostaFalsa:
    def __init__(self, status_code):
        self.status_code = status_code


def test_servidor_online_true_quando_responde_200():
    with mock.patch.object(api, "_requisitar") as requisitar_mock:
        requisitar_mock.return_value = _RespostaFalsa(200)
        assert api.servidor_online() is True


def test_servidor_online_false_quando_status_diferente_de_200():
    with mock.patch.object(api, "_requisitar") as requisitar_mock:
        requisitar_mock.return_value = _RespostaFalsa(503)
        assert api.servidor_online() is False


def test_servidor_online_false_em_qualquer_excecao_sem_propagar():
    with mock.patch.object(
        api, "_requisitar", side_effect=Exception("sem rede")
    ):
        assert api.servidor_online() is False


def test_header_definir_online_mostra_e_esconde_o_aviso():
    from design.header import Header

    header = Header("Loja Teste", "Fulano", "Administrador")

    # isHidden() (nao isVisible()) de proposito -- reflete a flag
    # explicita do proprio widget, sem depender da cadeia de
    # visibilidade de um ancestral que aqui nunca foi mostrado (ver
    # nota sobre QWidget.isVisible() em modo offscreen).
    assert header.lbl_status_conexao.isHidden() is True

    header.definir_online(False)
    assert header.lbl_status_conexao.isHidden() is False

    header.definir_online(True)
    assert header.lbl_status_conexao.isHidden() is True
