"""Abrir caixa: sugestao do troco da ultima sessao, selo de conferencia e historico."""
from datetime import datetime, timedelta

from design.privacidade import privacidade
from telas import abrir_caixa as tela
from telas.abrir_caixa import AbrirCaixaWindow, selo_sessao, troco_que_ficou


def _sessao(**kw):
    base = {"status": "FECHADO", "saldo_inicial": 150, "saldo_final": 1252.5,
            "valor_contado": 1250.0, "valor_guardado": 1000.0, "valor_retirado": 0,
            "usuario_nome": "André", "data_abertura": (datetime.now() - timedelta(days=1)).isoformat()}
    base.update(kw)
    return base


def test_troco_que_ficou_e_o_contado_menos_cofre_e_retirada():
    assert troco_que_ficou(_sessao()) == 250.0
    assert troco_que_ficou(_sessao(valor_retirado=50)) == 200.0
    # nao contou: vale o esperado
    assert troco_que_ficou(_sessao(valor_contado=None)) == 252.5
    # sessao ainda aberta nao tem "troco que ficou"
    assert troco_que_ficou(_sessao(status="ABERTO")) is None


def test_selo_conferido_faltou_sobrou():
    assert selo_sessao(_sessao(valor_contado=1252.5)) == ("Conferido", "sucesso")
    assert selo_sessao(_sessao()) == ("Faltou R$ 2,50", "erro")
    assert selo_sessao(_sessao(valor_contado=1260.0))[1] == "alerta"
    assert selo_sessao(_sessao(valor_contado=None)) == ("Fechado", "neutro")
    assert selo_sessao(_sessao(status="ABERTO")) == ("Aberto", "info")


def _dialogo(monkeypatch, financeiro=True):
    privacidade.definir_ocultos(False)
    monkeypatch.setattr(tela.api, "usuario_tem_permissao", lambda p: financeiro)
    monkeypatch.setattr(AbrirCaixaWindow, "carregar_historico", lambda self: None)
    return AbrirCaixaWindow()


def test_historico_mostra_sessoes_e_sugere_o_troco(monkeypatch):
    j = _dialogo(monkeypatch)
    assert j.cartao_sugestao.isHidden()

    j._ao_historico_sucesso([_sessao(), _sessao(valor_contado=1252.5), _sessao(status="ABERTO")])
    assert j.historico_layout.count() == 3
    assert not j.cartao_sugestao.isHidden()
    assert j.lbl_sugestao.text() == "Ficou R$ 250,00 na gaveta"

    j.bt_usar_sugestao.click()
    assert j.saldo == 250.0


def test_valor_rapido_preenche_e_destaca(monkeypatch):
    j = _dialogo(monkeypatch)
    j._chips[150].click()
    assert j.saldo == 150.0
    assert "2px" in j._chips[150].styleSheet() and "2px" not in j._chips[100].styleSheet()


def test_vendedor_nao_ve_historico_nem_sugestao(monkeypatch):
    j = _dialogo(monkeypatch, financeiro=False)
    assert not hasattr(j, "historico_layout")
    assert j.cartao_sugestao.isHidden()
    j._chips[100].click()
    assert j.saldo == 100.0


def test_sem_sessoes_mostra_aviso(monkeypatch):
    j = _dialogo(monkeypatch)
    j._ao_historico_sucesso([])
    assert j.historico_layout.count() == 1 and j.cartao_sugestao.isHidden()
