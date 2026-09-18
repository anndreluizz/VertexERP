"""Teste de services/worker.py::em_paralelo -- confere que os
resultados voltam na mesma ordem das chamadas (nao na ordem em que
cada thread termina) e que uma excecao numa das chamadas propaga pra
quem chamou em_paralelo, igual chamada sequencial normal faria."""
import time

import pytest

from services.worker import em_paralelo


def test_em_paralelo_preserva_ordem_mesmo_com_a_mais_lenta_primeiro():
    def lenta():
        time.sleep(0.05)
        return "lenta"

    def rapida():
        return "rapida"

    resultado = em_paralelo((lenta,), (rapida,), (lambda x: x, "com_arg"))

    assert resultado == ["lenta", "rapida", "com_arg"]


def test_em_paralelo_propaga_excecao():
    def falha():
        raise ValueError("erro de rede simulado")

    with pytest.raises(ValueError, match="erro de rede simulado"):
        em_paralelo((lambda: "ok",), (falha,))
