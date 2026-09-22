"""Testes de GraficoHeatmap (design/charts.py, Fase 6 Onda 11) --
so a logica de agregacao/estado (definir_dados, cor por intensidade),
sem renderizar de verdade (paintEvent nao roda fora de um show())."""
from design.charts import GraficoHeatmap


def _celula(dia, hora, quantidade, total):
    return {"dia_semana": dia, "hora": hora, "quantidade": quantidade, "total": total}


def _matriz_vazia(dias):
    return [
        _celula(dia, hora, 0, 0)
        for dia in dias
        for hora in range(24)
    ]


def test_definir_dados_preenche_matriz_e_maior_total():
    dias = ["Segunda", "Terça"]
    celulas = _matriz_vazia(dias)
    celulas[14] = _celula("Segunda", 14, 3, 150.0)   # segunda-feira, 14h
    celulas[24 + 9] = _celula("Terça", 9, 1, 50.0)    # terca-feira, 9h

    grafico = GraficoHeatmap()
    grafico.definir_dados(celulas)

    assert grafico._dias == ["Segunda", "Terça"]
    assert grafico._matriz[0][14]["total"] == 150.0
    assert grafico._matriz[1][9]["total"] == 50.0
    assert grafico._maior_total == 150.0


def test_cor_intensidade_zero_e_borda_maximo_e_primaria():
    from design import tokens

    grafico = GraficoHeatmap()
    grafico.definir_dados(_matriz_vazia(["Segunda"]))
    grafico._matriz[0][10]["total"] = 100.0
    grafico._maior_total = 100.0

    cor_vazia = grafico._cor_intensidade(0)
    cor_cheia = grafico._cor_intensidade(100.0)

    assert cor_vazia.name().lower() == tokens.BORDA.lower()
    assert cor_cheia.name().lower() == tokens.PRIMARIA.lower()


def test_sem_dados_nao_quebra_cor_intensidade():
    grafico = GraficoHeatmap()
    # _maior_total continua 0 (definir_dados nunca chamado) -- nao
    # pode dar ZeroDivisionError
    cor = grafico._cor_intensidade(0)
    assert cor is not None
