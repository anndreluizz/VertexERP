from datetime import datetime, timedelta

from app.models.movimento_fiado import MovimentoFiado
from app.repositories.movimento_fiado_repository import MovimentoFiadoRepository


def _mov(db, cliente, usuario, tipo, valor, dias_atras):
    db.add(MovimentoFiado(
        cliente_id=cliente.id, usuario_id=usuario.id, tipo=tipo,
        valor=valor, data=datetime.now() - timedelta(days=dias_atras),
    ))
    db.commit()


def _parados(db, cliente, dias=60):
    return [
        c for c, _s, _r in MovimentoFiadoRepository.listar_parados(db, dias)
        if c == cliente.id
    ]


def test_conta_do_ultimo_pagamento_e_compra_nova_nao_zera(db, cliente, usuario):
    _mov(db, cliente, usuario, "COMPRA", 100, 120)
    _mov(db, cliente, usuario, "PAGAMENTO", 10, 70)  # ultimo pagamento ha 70d
    _mov(db, cliente, usuario, "COMPRA", 50, 1)      # compra de ontem
    assert _parados(db, cliente) == [cliente.id]


def test_pagamento_recente_nao_cobra(db, cliente, usuario):
    _mov(db, cliente, usuario, "COMPRA", 100, 120)
    _mov(db, cliente, usuario, "PAGAMENTO", 10, 5)
    assert _parados(db, cliente) == []


def test_sem_pagamento_conta_da_ultima_compra(db, cliente, usuario):
    _mov(db, cliente, usuario, "COMPRA", 100, 90)
    _mov(db, cliente, usuario, "COMPRA", 50, 10)  # ultima compra recente
    assert _parados(db, cliente) == []
    assert _parados(db, cliente, dias=5) == [cliente.id]


def test_lembrete_usa_template_do_coexy(db, cliente, usuario, monkeypatch):
    from unittest.mock import MagicMock

    from app.services import whatsapp_lembrete_service as svc
    from app.services import whatsapp_service
    from app.services.configuracao_service import ConfiguracaoService

    config = ConfiguracaoService.buscar(db)
    config.whatsapp_ativo = True
    config.whatsapp_lembrete_fiado_ativo = True
    db.commit()

    monkeypatch.setenv("COEXY_CHANNEL_TOKEN", "tok")
    monkeypatch.setenv("COEXY_PHONE_NUMBER_ID", "123")
    post = MagicMock(return_value=MagicMock(status_code=200))
    monkeypatch.setattr(whatsapp_service.requests, "post", post)

    _mov(db, cliente, usuario, "COMPRA", 100, 90)
    svc.verificar_fiados_parados_e_notificar(db)

    url = post.call_args.args[0]
    corpo = post.call_args.kwargs["json"]
    assert url.endswith("/meta-proxy/123/messages")
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer tok"
    assert corpo["template"]["name"] == "cobranca_fiado"
    assert corpo["to"] == "5511999999999"
    textos = [p["text"] for p in corpo["template"]["components"][0]["parameters"]]
    assert textos == ["Cliente", "R$ 100,00"]
