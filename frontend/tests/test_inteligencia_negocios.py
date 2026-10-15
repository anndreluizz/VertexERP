"""Tela de Inteligencia de Negocios: periodos do filtro e preenchimento a
partir do /bi/resumo (numeros vem prontos do backend)."""
from datetime import date

from telas.inteligencia_negocios import InteligenciaNegocios, datas_do_periodo


def test_periodos_do_filtro():
    hoje = date(2026, 3, 15)
    assert datas_do_periodo("Hoje", hoje) == (hoje, hoje)
    assert datas_do_periodo("Últimos 7 dias", hoje) == (date(2026, 3, 9), hoje)
    assert datas_do_periodo("Últimos 30 dias", hoje) == (date(2026, 2, 14), hoje)
    assert datas_do_periodo("Mês atual", hoje) == (date(2026, 3, 1), hoje)
    assert datas_do_periodo("Mês anterior", hoje) == (date(2026, 2, 1), date(2026, 2, 28))
    assert datas_do_periodo("Mês anterior", date(2026, 1, 10)) == (
        date(2025, 12, 1), date(2025, 12, 31)
    )
    assert datas_do_periodo("Período personalizado", hoje) is None


def _resumo(lucro=None, recomendacoes=(), avisos=(), lojas=()):
    zero = {"quantidade": 0, "total": 0}
    return {
        "periodo": {"data_inicio": "2026-10-01", "data_fim": "2026-10-15",
                    "loja_nome": "Todas as lojas", "gerado_em": "2026-10-15T10:23:00"},
        "vendas": {"faturamento_liquido": 100, "faturamento_bruto": 110, "devolucoes": 10,
                   "quantidade": 2, "ticket_medio": 50, "a_vista": 70, "a_prazo": 30,
                   "lucro_bruto": lucro, "formas_pagamento": [
                       {"forma_pagamento": "PIX", "quantidade": 1, "total": 70}],
                   "mais_vendidos": [{"produto": "Caneta", "quantidade": 3, "total": 9}]},
        "recebimentos": {"fiado_recebido": 5},
        "caixa": {"dinheiro_nas_gavetas": 0, "entrou_no_periodo": 75},
        "fiado": {"saldo_em_aberto": 40, "clientes_devendo": 1,
                  "faixas_atraso": [{"de_dias": 181, "ate_dias": None, "clientes": 1, "total": 40}],
                  "maiores_devedores": [{"nome": "Ana", "saldo": 40, "dias_em_atraso": 200,
                                         "tem_telefone": False}]},
        "contas_pagar": {"vencidas": zero, "proximos_7_dias": zero, "proximos_30_dias": zero,
                         "proximas": [{"vencimento": "2026-10-20", "descricao": None, "valor": 8}]},
        "previsao_30_dias": {"saldo_previsto": -3, "entradas_estimadas": 5,
                             "saidas_previstas": 8, "observacao": "estimativa"},
        "lojas": list(lojas),
        "avisos": list(avisos),
        "recomendacoes": list(recomendacoes),
    }


def test_preenche_cards_tabelas_e_recomendacoes():
    tela = InteligenciaNegocios()
    rec = {"prioridade": "critica", "problema": "Falta dinheiro", "evidencias": ["X"],
           "impacto": "I", "acao": "A", "prazo": "Hoje", "indicador": "Y"}

    tela._ao_carregar(_resumo(recomendacoes=[rec], avisos=["sem custo"]))

    assert tela.card_lucro.lbl_valor.text() == "—"
    assert "01/10/2026 a 15/10/2026" in tela.lbl_periodo.text()
    assert tela.tabela_devedores.item(0, 0).text() == "Ana"
    assert tela.tabela_devedores.item(0, 3).text() == "não"
    assert tela.tabela_faixas.item(0, 0).text() == "mais de 180 dias"
    assert tela.tabela_contas.item(0, 1).text() == "—"
    assert tela.secao_recomendacoes.corpo.count() == 1
    assert not tela.secao_avisos.isHidden()
    assert tela.secao_lojas.isHidden()


def test_sem_recomendacoes_mostra_mensagem():
    tela = InteligenciaNegocios()
    tela._ao_carregar(_resumo(lucro=12))

    assert tela.secao_recomendacoes.corpo.count() == 1
    assert tela.secao_avisos.isHidden()
    assert tela.card_lucro.lbl_valor.text() != "—"


def test_erro_de_permissao_aparece_na_tela():
    tela = InteligenciaNegocios()
    tela._ao_erro(Exception("Você não tem permissão"))

    assert not tela.lbl_erro.isHidden()
    assert "permissão" in tela.lbl_erro.text()


def test_valor_digitado():
    from telas.inteligencia_negocios import valor_digitado
    assert valor_digitado("10.000,50") == 10000.5
    assert valor_digitado("R$ 800") == 800
    assert valor_digitado("1500.5") == 1500.5
    assert valor_digitado("0") == 0
    assert valor_digitado("-5") is None
    assert valor_digitado("abc") is None
    assert valor_digitado("") is None


def test_mostra_dinheiro_guardado():
    tela = InteligenciaNegocios()
    dados = _resumo()
    tela._ao_carregar(dados)
    assert "não informado" in tela.lbl_guardado.text()

    dados["caixa"].update(dinheiro_guardado=1234.5, dinheiro_guardado_em="2026-10-15T14:30:00")
    tela._ao_carregar(dados)
    assert "R$ 1.234,50" in tela.lbl_guardado.text()
    assert "15/10/2026" in tela.lbl_guardado.text()
