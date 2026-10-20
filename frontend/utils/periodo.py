"""Meses fechados pros combos de periodo ("Agosto/2026", "Julho/2026"...).
Na loja se olha tudo por mes; "Este mes"/"Mes anterior" ja' existem em
cada tela, entao a lista comeca dois meses atras."""

from calendar import monthrange
from datetime import date, timedelta

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def rotulo_mes(dia):
    return f"{MESES[dia.month - 1]}/{dia.year}"


def meses_recentes(hoje=None, quantos=14):
    """Este mes, o anterior e mais `quantos - 2` -- pra telas sem
    "Este mes"/"Mes anterior" proprios."""
    hoje = hoje or date.today()
    anterior = hoje.replace(day=1) - timedelta(days=1)
    return [rotulo_mes(hoje), rotulo_mes(anterior)] + meses_anteriores(hoje, quantos - 2)


def meses_seguintes(hoje=None, quantos=3):
    """Proximos meses (contas a vencer): "Novembro/2026", ..."""
    hoje = hoje or date.today()
    ano, mes, rotulos = hoje.year, hoje.month, []
    for _ in range(quantos):
        mes += 1
        if mes == 13:
            ano, mes = ano + 1, 1
        rotulos.append(f"{MESES[mes - 1]}/{ano}")
    return rotulos


def meses_anteriores(hoje=None, quantos=12):
    """Rotulos dos `quantos` meses antes do mes anterior, do mais novo
    pro mais velho."""
    hoje = hoje or date.today()
    ano, mes = hoje.year, hoje.month
    rotulos = []
    for _ in range(quantos + 1):
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
        rotulos.append(f"{MESES[mes - 1]}/{ano}")
    return rotulos[1:]  # o primeiro e' o "Mes anterior"


def intervalo_mes(rotulo):
    """"Agosto/2026" -> (1/8/2026, 31/8/2026); outro texto -> None."""
    nome, _, ano = str(rotulo).partition("/")
    if nome not in MESES or not ano.isdigit():
        return None
    ano, mes = int(ano), MESES.index(nome) + 1
    return date(ano, mes, 1), date(ano, mes, monthrange(ano, mes)[1])
