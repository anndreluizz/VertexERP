"""A janela principal nao cria as 17 telas no arranque: so' na 1a vez que
abrem (criar tudo de uma vez travava ~5 s, "Vertex nao esta respondendo")."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from telas import principal
from telas.principal import PrincipalWindow


class _TelaFalsa(QWidget):
    voltar = Signal()
    tarefa_escolhida = Signal(str)
    troca_iniciada = Signal(float, object)
    loja_atualizada = Signal(str)

    criadas = []

    def __init__(self, *a, **k):
        super().__init__()
        _TelaFalsa.criadas.append(self)

    def carregar(self, *a, **k):
        pass


def _janela(monkeypatch):
    _TelaFalsa.criadas = []
    monkeypatch.setattr(principal.api, "usuario_e_admin", lambda: True)
    monkeypatch.setattr(principal.api, "usuario_tem_permissao", lambda _p: True)
    monkeypatch.setattr(principal.api, "cargo_usuario", lambda _i: "Admin")
    monkeypatch.setattr(
        PrincipalWindow, "_FABRICAS",
        {nome: (lambda s: _TelaFalsa()) for nome in PrincipalWindow._FABRICAS},
    )
    return PrincipalWindow({"nome": "Ana", "id": 1, "admin": True}, {"nome_loja": "Loja"})


def test_arranque_nao_cria_nenhuma_tela(monkeypatch):
    j = _janela(monkeypatch)
    assert _TelaFalsa.criadas == []
    assert j.abas.abertas == ["modulos"]


def test_tela_e_criada_na_primeira_abertura_e_reaproveitada(monkeypatch):
    j = _janela(monkeypatch)

    j._navegar("clientes")
    assert len(_TelaFalsa.criadas) == 1
    assert j.paginas.currentWidget() is j.clientes

    j._navegar("modulos")
    j._navegar("clientes")
    assert len(_TelaFalsa.criadas) == 1     # nao recria


def test_voltar_da_tela_criada_sob_demanda_fecha_a_aba(monkeypatch):
    j = _janela(monkeypatch)
    j._navegar("produtos")
    assert j.abas.atual == "produtos"

    j.produtos.voltar.emit()
    assert j.abas.atual == "modulos"


def test_atributo_desconhecido_continua_dando_attribute_error(monkeypatch):
    j = _janela(monkeypatch)
    try:
        j.nao_existe
    except AttributeError:
        return
    raise AssertionError("deveria levantar AttributeError")
