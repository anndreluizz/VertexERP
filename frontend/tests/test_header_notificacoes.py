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


def test_categoria_e_tempo_relativo():
    from datetime import datetime, timedelta
    from design import header as h
    assert h._categoria("Backup falhou")[0] == "download"
    assert h._categoria("Algo sem palavra-chave")[0] == "bell"
    agora = datetime.now()
    assert h._tempo_relativo((agora - timedelta(minutes=5)).isoformat()) == "há 5 min"
    assert h._grupo_do_dia((agora - timedelta(hours=30)).isoformat()) == "Ontem"


def test_central_abas_e_marcar_todas():
    from datetime import datetime
    from design import header as h
    agora = datetime.now().isoformat()
    notas = [{"id": i, "titulo": "Caixa", "corpo": "x", "lida": i == 1, "criado_em": agora} for i in (1, 2, 3)]
    header = _header(admin=True, pendentes=[{"id": 9, "descricao": "Desconto", "criado_em": agora}], nao_lidas=2)
    central = h._Central(header, notas, [{"id": 9, "descricao": "Desconto", "criado_em": agora}])
    cartoes = central.findChildren(h._CartaoNotificacao)
    assert len(cartoes) == 3 and len(central.findChildren(h._CartaoAprovacao)) == 1
    central._trocar_aba("nao")
    assert len(central.findChildren(h._CartaoNotificacao)) == 2
    central._trocar_aba("aprov")
    assert len(central.findChildren(h._CartaoNotificacao)) == 0
    with mock.patch("design.header.notificacao_service.marcar_todas_lidas"), \
         mock.patch("design.header.notificacao_service.contagem_nao_lidas", return_value=0):
        header._popover_notificacoes = central
        header._marcar_todas_notificacoes_lidas()
    assert all(n["lida"] for n in notas)
