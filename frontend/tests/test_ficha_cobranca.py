from datetime import datetime, timedelta
from unittest import mock

from telas.ficha_cliente import ficha as f


def _ficha(_qapp):
    cli = {"id": 1, "nome": "Maria Souza", "telefone": "1", "limite_credito": 800}
    with mock.patch.object(f.FichaClienteDialog, "carregar", lambda s: None):
        return f.FichaClienteDialog(cli)


def _mov(tipo, dias, valor):
    return {"tipo": tipo, "valor": valor, "data": (datetime.now() - timedelta(days=dias)).isoformat()}


def test_aviso_de_cobranca_so_com_saldo_e_mais_de_60_dias(_qapp):
    d = _ficha(_qapp)
    d.show()
    d._atualizar_stats([_mov("COMPRA", 90, 100)], 100)
    assert d.aviso_cobranca.isVisible() and "90 dias" in d.lbl_cobranca_titulo.text()
    d._atualizar_stats([_mov("COMPRA", 90, 100), _mov("PAGAMENTO", 10, 50)], 50)
    assert not d.aviso_cobranca.isVisible()
    d._atualizar_stats([_mov("COMPRA", 90, 100)], 0)
    assert not d.aviso_cobranca.isVisible()


def test_barra_do_limite_acompanha_o_saldo(_qapp):
    d = _ficha(_qapp)
    d.show()
    d.barra_limite.resize(200, 8)
    d.barra_limite.definir_fracao(412.5 / 800)
    assert 100 <= d.barra_limite._fill.width() <= 106
    d.barra_limite.definir_fracao(2.0)  # passou do limite: enche e para
    assert d.barra_limite._fill.width() == 200
