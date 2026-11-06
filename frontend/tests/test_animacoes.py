"""Numeros dos cards contam ate' o valor e terminam no texto exato."""
from unittest import mock

from PySide6.QtWidgets import QLabel

from design import animations
from design.privacidade import privacidade


def _rodar_ate_o_fim(rotulo):
    anim = rotulo._contar_anim
    anim.setCurrentTime(anim.duration() // 2)
    meio = rotulo.text()
    anim.setCurrentTime(anim.duration())
    return meio


def test_conta_moeda_e_termina_exato(monkeypatch):
    monkeypatch.setattr(privacidade, "ocultos", False)
    with mock.patch.object(animations, "movimento_reduzido", return_value=False):
        rotulo = QLabel()
        assert animations.contar(rotulo, "R$ 1.284,50")
        meio = _rodar_ate_o_fim(rotulo)
    assert meio.startswith("R$ ") and meio != "R$ 1.284,50"
    assert rotulo.text() == "R$ 1.284,50"


def test_quantidade_com_sufixo():
    with mock.patch.object(animations, "movimento_reduzido", return_value=False):
        rotulo = QLabel()
        assert animations.contar(rotulo, "14 produtos")
        _rodar_ate_o_fim(rotulo)
    assert rotulo.text() == "14 produtos"


def test_texto_que_nao_e_numero_so_troca():
    with mock.patch.object(animations, "movimento_reduzido", return_value=False):
        for texto in ("—", "05/11/2026", "Caixa aberto às 08:02"):
            rotulo = QLabel()
            assert not animations.contar(rotulo, texto)
            assert rotulo.text() == texto


def test_olhinho_fechado_continua_mascara(monkeypatch):
    monkeypatch.setattr(privacidade, "ocultos", True)
    with mock.patch.object(animations, "movimento_reduzido", return_value=False):
        rotulo = QLabel()
        animations.contar(rotulo, "R$ 642,00")
        meio = _rodar_ate_o_fim(rotulo)
    assert meio == rotulo.text() == "R$ ••••"


def test_formatar_br():
    assert animations._formatar_br(1284.5, 2) == "1.284,50"
    assert animations._formatar_br(7, 0) == "7"
