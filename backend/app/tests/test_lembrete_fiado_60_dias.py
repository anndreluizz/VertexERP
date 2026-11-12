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
