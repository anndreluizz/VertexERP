"""Tela do Caixa (redesign): filtros de movimento, aviso de caixa aberto ha muito
tempo, formas de entrada, sem caixa e ultimo fechamento."""
from datetime import datetime, timedelta

import pytest

from design.privacidade import privacidade
from telas import caixa as tela
from telas.caixa import (
    Caixa, _minutos_aberto, _tempo_aberto, data_por_extenso, filtrar_movimentos, saudacao,
)

MOVS = [
    {"tipo": "VENDA", "forma_pagamento": "DINHEIRO", "valor": 89.8, "descricao": "Venda #1", "data": "2026-11-15T10:42:00"},
    {"tipo": "VENDA", "forma_pagamento": "PRAZO", "valor": 156.4, "descricao": "Venda #2", "data": "2026-11-15T09:58:00"},
    {"tipo": "SANGRIA", "forma_pagamento": None, "valor": 300.0, "descricao": "Cofre", "data": "2026-11-15T10:05:00"},
    {"tipo": "SUPRIMENTO", "forma_pagamento": None, "valor": 50.0, "descricao": "Troco", "data": "2026-11-15T08:20:00"},
]
RESUMO = {"saldo_inicial": 150, "vendas_dinheiro": 842.5, "vendas_pix": 615.9, "vendas_cartao": 1204.3,
          "vendas_prazo": 156.4, "sangrias": 300, "total_previsto": 1252.5}


def _caixa(monkeypatch, permissoes=True):
    privacidade.definir_ocultos(False)
    monkeypatch.setattr(tela.api, "usuario_tem_permissao", lambda p: permissoes)
    monkeypatch.setattr(tela.api, "nome_usuario", lambda: "André Lopes")
    monkeypatch.setattr(Caixa, "carregar", lambda self: None)      # nao busca no servidor
    return Caixa()


def test_filtros_separam_vendas_fiado_e_sangria():
    assert [m["descricao"] for m in filtrar_movimentos(MOVS, ("VENDA",))] == ["Venda #1"]
    assert [m["descricao"] for m in filtrar_movimentos(MOVS, ("VENDA_FIADO",))] == ["Venda #2"]
    assert len(filtrar_movimentos(MOVS, ("SANGRIA", "SUPRIMENTO"))) == 2
    assert len(filtrar_movimentos(MOVS, None)) == 4


def test_saudacao_e_data_por_extenso():
    assert saudacao(datetime(2026, 11, 15, 8)) == "Bom dia"
    assert saudacao(datetime(2026, 11, 15, 14)) == "Boa tarde"
    assert saudacao(datetime(2026, 11, 15, 21)) == "Boa noite"
    assert data_por_extenso(datetime(2026, 11, 15)) == "DOMINGO · 15 DE NOVEMBRO"


def test_tempo_aberto_continua_igual():
    agora = datetime(2026, 11, 15, 12, 0)
    assert _tempo_aberto("2026-11-15T11:25:00", agora) == "há 35 min"
    assert _tempo_aberto("2026-11-15T04:48:00", agora) == "há 7h12"
    assert _minutos_aberto("2026-11-15T04:48:00", agora) == 432
    assert _tempo_aberto("lixo") == "" and _minutos_aberto("lixo") == 0


def test_chips_contam_e_escondem_o_que_nao_existe(monkeypatch):
    c = _caixa(monkeypatch)
    c._movimentos = MOVS
    c._aplicar_filtro_movimento()

    visiveis = {rotulo: not bt.isHidden() for bt, rotulo, _ in c._chips_mov.values()}
    assert visiveis["Todos"] and visiveis["Vendas"] and visiveis["Fiado"]
    assert not visiveis["Estornos"] and not visiveis["Contas pagas"]
    assert c._chips_mov[0][0].text() == "Todos   4"

    c._escolher_filtro_movimento(2)     # Sangrias e suprimentos
    assert c.lista_movimentos.count() == 2

    # recarregou sem esse tipo: o filtro escolhido some e volta pra Todos
    c._movimentos = [m for m in MOVS if m["tipo"] == "VENDA"]
    c._aplicar_filtro_movimento()
    assert c._filtro_mov == 0 and c.lista_movimentos.count() == 2


def test_aviso_so_com_caixa_aberto_ha_muito_tempo(monkeypatch):
    c = _caixa(monkeypatch)
    recente = (datetime.now() - timedelta(hours=7)).isoformat()
    c._mostrar_abertura({"data_abertura": recente})
    assert c.faixa_atencao.isHidden()

    longo = (datetime.now() - timedelta(hours=21)).isoformat()
    c._mostrar_abertura({"data_abertura": longo})
    assert not c.faixa_atencao.isHidden()

    c._mostrar_abertura({"data_abertura": longo, "vencido": True})
    assert not c.faixa_atencao.isHidden()


def test_carregar_sucesso_preenche_numeros_e_formas(monkeypatch):
    c = _caixa(monkeypatch)
    c._ao_carregar_sucesso(({"id": 1, "data_abertura": datetime.now().isoformat()}, RESUMO, MOVS))
    assert c.paginas.currentWidget() is c.pagina_com_caixa
    assert c._esperado == 1252.5
    assert c.lbl_total_entrou.text() == "R$ 2.662,70"     # sem o fiado
    assert not hasattr(c, "campo_contado")                # a conferencia ficou no Fechar caixa


def test_vendedor_nao_ve_totais_nem_formas(monkeypatch):
    c = _caixa(monkeypatch, permissoes=False)
    assert c.secao_kpis.isHidden() and c.cartao_formas.isHidden()
    assert c._esperado_ou_none() is None


def test_sem_caixa_mostra_boas_vindas_e_ultimo_fechamento(monkeypatch):
    c = _caixa(monkeypatch)
    monkeypatch.setattr(tela, "rodar_em_thread", lambda *a, **k: None)
    c._ao_carregar_sucesso((None, None, []))
    assert c.paginas.currentWidget() is c.pagina_sem_caixa
    assert c.lbl_saudacao.text().endswith("André")
    assert c.secao_ultimo.isHidden()

    ontem = (datetime.now() - timedelta(days=1)).replace(hour=19, minute=40).isoformat()
    c._ao_ultimo_fechamento_sucesso([
        {"status": "ABERTO", "data_abertura": datetime.now().isoformat()},
        {"status": "FECHADO", "data_abertura": ontem, "data_fechamento": ontem, "saldo_final": 1252.5,
         "valor_contado": 1252.5, "valor_guardado": 1000, "valor_retirado": 0, "usuario_nome": "André"},
    ])
    assert not c.secao_ultimo.isHidden()
    (v1, d1), (v2, _), (v3, d3) = c._tiles_ultimo
    assert v1.text() == "Ontem, 19:40" and d1.text() == "por André"
    assert v2.text() == "R$ 252,50"
    assert v3.text() == "Bateu certinho" and d3.text() == "diferença R$ 0,00"

    # nenhuma sessao fechada: nao inventa nada
    c.secao_ultimo.hide()
    c._ao_ultimo_fechamento_sucesso([{"status": "ABERTO"}])
    assert c.secao_ultimo.isHidden()
