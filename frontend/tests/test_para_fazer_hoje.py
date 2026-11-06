"""Início: cartoes "Para fazer hoje" (fiado atrasado, repor, boletos)."""
from datetime import date, datetime, timedelta

from telas.para_fazer_hoje import ParaFazerHoje, tarefas_do_dia

HOJE = date.today()


def _iso(dias_atras):
    return (datetime.now() - timedelta(days=dias_atras)).isoformat()


def test_fiado_atrasado_so_depois_de_2_meses_e_ignora_negativado():
    clientes = [
        {"id": 1, "nome": "A", "criado_em": _iso(400)},
        {"id": 2, "nome": "B", "criado_em": _iso(400)},
        {"id": 3, "nome": "C", "criado_em": _iso(400), "negativado": True},
    ]
    movs = [
        {"cliente_id": 1, "tipo": "COMPRA", "valor": 100, "data": _iso(75), "criado_em": _iso(75)},
        {"cliente_id": 2, "tipo": "COMPRA", "valor": 50, "data": _iso(40), "criado_em": _iso(40)},
        {"cliente_id": 3, "tipo": "COMPRA", "valor": 80, "data": _iso(200), "criado_em": _iso(200)},
    ]
    tarefas = tarefas_do_dia([], [], clientes, movs)
    assert [t["id"] for t in tarefas] == ["fiado"]
    assert tarefas[0]["titulo"] == "1 cliente com fiado atrasado"
    assert "R$ 100,00" in tarefas[0]["detalhe"]


def test_repor_e_boletos_e_vendedor_nao_ve_boletos():
    produtos = [
        {"nome": "x", "estoque": 0, "estoque_minimo": 2},
        {"nome": "y", "estoque": 2, "estoque_minimo": 2},
        {"nome": "z", "estoque": 9, "estoque_minimo": 2},
        {"nome": "inativo", "estoque": 0, "estoque_minimo": 5, "ativo": False},
    ]
    boletos = [
        {"status": "PENDENTE", "valor": 100, "data_vencimento": str(HOJE - timedelta(days=1))},
        {"status": "PENDENTE", "valor": 50, "data_vencimento": str(HOJE + timedelta(days=3))},
        {"status": "PENDENTE", "valor": 999, "data_vencimento": str(HOJE + timedelta(days=30))},
        {"status": "PAGO", "valor": 10, "data_vencimento": str(HOJE)},
    ]
    tarefas = {t["id"]: t for t in tarefas_do_dia(produtos, boletos, [], [], hoje=HOJE)}
    assert tarefas["estoque"]["titulo"] == "2 produtos para repor"
    assert tarefas["estoque"]["detalhe"] == "1 sem estoque"
    assert tarefas["boletos"]["titulo"] == "1 boleto vencido"
    assert tarefas["boletos"]["detalhe"] == "R$ 150,00 ao todo · mais 1 a vencer"

    vendedor = tarefas_do_dia(produtos, boletos, [], [], hoje=HOJE, financeiro=False)
    assert "boletos" not in {t["id"] for t in vendedor}


def test_sem_nada_mostra_tudo_em_dia_e_botao_emite():
    bloco = ParaFazerHoje()
    bloco.definir([])
    assert len(bloco.cartoes) == 1 and not hasattr(bloco.cartoes[0], "botao")

    escolhidas = []
    bloco.acao.connect(escolhidas.append)
    bloco.definir([{"id": "estoque", "titulo": "t", "detalhe": "d", "acao": "Ver", "variante": "alerta"}])
    bloco.cartoes[0].botao.click()
    assert escolhidas == ["estoque"]
