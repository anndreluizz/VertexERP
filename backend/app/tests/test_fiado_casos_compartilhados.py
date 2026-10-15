"""Mesmos casos de fiado que o PC e o app (testes_compartilhados/
fiado_casos.json): saldo pelo SQL do repositorio e atraso pela regra
FIFO da Inteligencia de Negocios. Se um dos tres calcular diferente, o
CI barra."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.cliente import Cliente
from app.models.movimento_fiado import MovimentoFiado
from app.repositories.movimento_fiado_repository import MovimentoFiadoRepository
from app.services.bi_service import _compra_mais_antiga_em_aberto

_ARQUIVO = Path(__file__).resolve().parents[3] / "testes_compartilhados" / "fiado_casos.json"
CASOS = json.loads(_ARQUIVO.read_text(encoding="utf-8"))["casos"]


@pytest.mark.parametrize("caso", CASOS, ids=[c["nome"] for c in CASOS])
def test_caso_compartilhado(caso, db, usuario):
    agora = datetime.now()
    cliente = Cliente(nome=caso["nome"], email="caso@x.com", ativo=True)
    db.add(cliente)
    db.commit()
    movs = [
        MovimentoFiado(cliente_id=cliente.id, usuario_id=usuario.id, tipo=tipo,
                       valor=Decimal(str(valor)), data=agora - timedelta(days=dias))
        for tipo, valor, dias in caso["movimentos"]
    ]
    db.add_all(movs)
    db.commit()

    saldo = MovimentoFiadoRepository.saldo_por_cliente(db, cliente.id)
    assert float(saldo) == caso["saldo"]

    desde = _compra_mais_antiga_em_aberto(movs) if saldo > 0 else None
    dias = (agora - desde).days if desde else None
    assert dias == caso["dias_em_atraso"]
