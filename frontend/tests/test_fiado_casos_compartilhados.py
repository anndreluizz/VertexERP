"""Mesmos casos de fiado que o servidor e o app (testes_compartilhados/
fiado_casos.json) -- o PC classifica clientes por cliente_analise."""
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from services import cliente_analise

_ARQUIVO = Path(__file__).resolve().parents[2] / "testes_compartilhados" / "fiado_casos.json"
CASOS = json.loads(_ARQUIVO.read_text(encoding="utf-8"))["casos"]


@pytest.mark.parametrize("caso", CASOS, ids=[c["nome"] for c in CASOS])
def test_caso_compartilhado(caso):
    agora = datetime.now()
    movs = [
        {"tipo": tipo, "valor": valor, "data": (agora - timedelta(days=dias)).isoformat()}
        for tipo, valor, dias in caso["movimentos"]
    ]

    agr = cliente_analise.calcular_agregados({}, movs)

    assert round(agr["saldo_devedor"], 2) == caso["saldo"]
    assert agr["dias_em_atraso"] == caso["dias_em_atraso"]
