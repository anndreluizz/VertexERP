"""Alerta no canto da tela quando chega notificação nova (ver
design/header.py::_alertar_novas)."""
from unittest import mock

from design import header as modulo


def _n(id_, lida=False):
    return {"id": id_, "titulo": f"Aviso {id_}", "corpo": "texto", "lida": lida}


def _header():
    with mock.patch.object(modulo.notificacao_service, "contagem_nao_lidas", return_value=0),             mock.patch.object(modulo.notificacao_service, "listar", return_value=[_n(5)]):
        return modulo.Header("Loja Teste", "Fulano", "Administrador")


def test_ao_abrir_nao_alerta_as_antigas(_qapp):
    with mock.patch.object(modulo, "_AlertaNotificacao") as alerta:
        h = _header()
    alerta.assert_not_called()
    assert h._ultima_notificacao_id == 5


def test_notificacao_nova_mostra_alerta_com_som(_qapp):
    h = _header()
    with mock.patch.object(modulo.notificacao_service, "listar", return_value=[_n(7), _n(6), _n(5)]),             mock.patch.object(modulo, "_AlertaNotificacao") as alerta,             mock.patch.object(modulo, "_tocar_som") as som:
        h._alertar_novas()

    assert alerta.call_args.args[0] == "Aviso 7 (+1)"
    som.assert_called_once()

    with mock.patch.object(modulo.notificacao_service, "listar", return_value=[_n(7), _n(6)]),             mock.patch.object(modulo, "_AlertaNotificacao") as alerta:
        h._alertar_novas()
    alerta.assert_not_called()


def test_nova_ja_lida_em_outro_lugar_nao_alerta(_qapp):
    h = _header()
    with mock.patch.object(modulo.notificacao_service, "listar", return_value=[_n(6, lida=True)]),             mock.patch.object(modulo, "_AlertaNotificacao") as alerta:
        h._alertar_novas()
    alerta.assert_not_called()
