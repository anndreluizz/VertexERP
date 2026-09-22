"""Testes do sininho de notificações no Header (Fase 6, Onda 8) --
badge combinado (aprovações pendentes + notificações não lidas) e o
clique numa notificação marcando ela como lida."""
from unittest import mock

from design.header import Header


def _header(admin=False, pendentes=None, nao_lidas=0):
    with mock.patch(
        "design.header.listar_pendentes", return_value=pendentes or []
    ), mock.patch(
        "design.header.notificacao_service.contagem_nao_lidas",
        return_value=nao_lidas,
    ):
        return Header("Loja Teste", "Fulano", "Vendedor", admin=admin)


def test_badge_some_quando_nao_ha_nada_pendente():
    header = _header(admin=True, pendentes=[], nao_lidas=0)
    assert header._badge_aprovacoes.isHidden() is True


def test_badge_mostra_notificacoes_nao_lidas_mesmo_sem_ser_admin():
    header = _header(admin=False, nao_lidas=3)
    assert header._badge_aprovacoes.isHidden() is False
    assert header._badge_aprovacoes.text() == "3"


def test_badge_soma_aprovacoes_e_notificacoes_pra_admin():
    header = _header(
        admin=True, pendentes=[{"id": 1}, {"id": 2}], nao_lidas=1
    )
    assert header._badge_aprovacoes.text() == "3"


def test_clicar_em_notificacao_marca_como_lida_e_atualiza_badge():
    header = _header(admin=False, nao_lidas=1)

    notificacao = {
        "id": 10, "titulo": "Título", "corpo": "Corpo",
        "lida": False, "criado_em": "2026-09-22T10:00:00",
    }

    with mock.patch(
        "design.header.notificacao_service.marcar_lida"
    ) as marcar_mock, mock.patch(
        "design.header.notificacao_service.contagem_nao_lidas", return_value=0
    ):
        from design.header import _CartaoNotificacao

        cartao = _CartaoNotificacao(notificacao, on_lida=header._atualizar_contagem_notificacoes)
        cartao._marcar_lida()

    marcar_mock.assert_called_once_with(10)
    assert header._badge_aprovacoes.isHidden() is True
