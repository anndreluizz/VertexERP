"""Retencao e validacao do backup automatico do launcher.py (fica aqui
porque este e' o job de CI que roda em Windows -- launcher.py usa
ctypes.windll). Foi um backup quebrado que fez a loja perder 3
semanas de dados: essa logica nao pode regredir calada."""

import importlib.util
import os
from datetime import datetime, timedelta

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def launcher():
    spec = importlib.util.spec_from_file_location(
        "launcher", os.path.join(_RAIZ, "launcher.py")
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _backups(agora, horas_atras):
    return [(f"b_{h}.sql", agora - timedelta(hours=h)) for h in horas_atras]


def test_relogio_adiantado_nao_apaga_todos_os_backups(launcher):
    agora = datetime(2026, 9, 26, 12, 0)
    arquivos = _backups(agora, range(0, 20 * 4, 4))  # 20 backups, 4h entre eles

    # relogio pulou 5 anos pra frente: tudo "tem mais de 30 dias"
    apagar = launcher._backups_para_apagar(arquivos, agora + timedelta(days=5 * 365))

    mantidos = {c for c, _ in arquivos} - set(apagar)
    assert len(mantidos) == launcher.MINIMO_BACKUPS_MANTIDOS
    # e sao justamente os mais recentes
    assert mantidos == {c for c, _ in arquivos[: launcher.MINIMO_BACKUPS_MANTIDOS]}


def test_entre_7_e_30_dias_fica_o_ultimo_de_cada_dia(launcher):
    agora = datetime(2026, 9, 26, 12, 0)
    recentes = _backups(agora, range(0, 12))  # piso de 10 + folga
    dia_antigo = agora - timedelta(days=10)
    antigos = [
        ("d10_08h.sql", dia_antigo.replace(hour=8)),
        ("d10_16h.sql", dia_antigo.replace(hour=16)),
        ("d10_12h.sql", dia_antigo.replace(hour=12)),
    ]

    apagar = launcher._backups_para_apagar(recentes + antigos, agora)

    assert "d10_16h.sql" not in apagar
    assert {"d10_08h.sql", "d10_12h.sql"} <= set(apagar)


def test_validar_dump_recusa_arquivo_truncado(launcher, tmp_path):
    truncado = tmp_path / "t.sql.tmp"
    truncado.write_text("-- dump\nCOPY public.vendas (id) FROM stdin;\n1\n")

    with pytest.raises(RuntimeError):
        launcher._validar_dump(str(truncado))

    vazio = tmp_path / "v.sql.tmp"
    vazio.write_text("")

    with pytest.raises(RuntimeError):
        launcher._validar_dump(str(vazio))


def test_validar_dump_aceita_dump_completo(launcher, tmp_path):
    completo = tmp_path / "c.sql.tmp"
    completo.write_text("-- dump\n--\n-- PostgreSQL database dump complete\n--\n")

    launcher._validar_dump(str(completo))


def test_trava_de_instancia_unica_bloqueia_a_segunda(launcher):
    # mutex do Windows (nao arquivo com PID): o SO libera sozinho
    # quando o processo morre, entao nunca fica trava orfa apos reboot
    assert launcher.obter_trava() is True
    assert launcher.obter_trava() is False
