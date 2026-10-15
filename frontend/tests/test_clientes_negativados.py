"""Clientes: negativados ficam numa aba so' deles e fora de todo o resto
(contagens e "a receber") -- a divida deles e' dinheiro perdido."""
from datetime import datetime

from services import cliente_analise
from telas.clientes import Clientes
from telas.selecionar_cliente import situacao_fiado


def _dados():
    hoje = datetime.now().isoformat()
    clientes = [
        {"id": 1, "nome": "Ana", "ativo": True, "negativado": False},
        {"id": 2, "nome": "Rosilene", "ativo": True, "negativado": True},
    ]
    movs = {
        1: [{"tipo": "COMPRA", "valor": 50, "data": hoje}],
        2: [{"tipo": "COMPRA", "valor": 150, "data": hoje},
            {"tipo": "PERDA", "valor": 150, "data": hoje}],
    }
    agrs = {}
    for c in clientes:
        agrs[c["id"]] = cliente_analise.calcular_agregados(c, movs[c["id"]])
        c["saldo_fiado"] = agrs[c["id"]]["saldo_devedor"]
    return clientes, agrs, {}, 0.0, movs


def test_aba_negativados_separada():
    w = Clientes()
    w._ao_carregar_sucesso(_dados())

    assert [c["nome"] for c in w._clientes_filtrados] == ["Ana"]
    assert w.botoes_status["TODOS"].text().endswith("1")
    assert w.botoes_status["NEGATIVADOS"].text().endswith("1")

    w.selecionar_status("NEGATIVADOS")
    assert [c["nome"] for c in w._clientes_filtrados] == ["Rosilene"]


def test_pdv_mostra_negativado():
    assert situacao_fiado({"negativado": True})[0].startswith("NEGATIVADO")
