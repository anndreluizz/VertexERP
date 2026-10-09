"""Tela de Vendas (histórico + total por vendedora), janela de
devolução/troca e o crédito de troca no PDV/pagamento."""
from unittest import mock

from PySide6.QtWidgets import QMessageBox

from services import api
from telas.devolucao_dialog import DevolucaoDialog, fator_desconto
from telas.pagamento import PagamentoWindow
from telas.vendas import Vendas
from tests.test_pdv import _tela_pdv


class _Resposta:
    def __init__(self, status_code, corpo):
        self.status_code = status_code
        self._corpo = corpo
        self.text = str(corpo)

    def json(self):
        return self._corpo


def _venda(**extra):
    venda = {
        "id": 7,
        "data": "2026-10-09T10:30:00",
        "cliente_id": 3,
        "cliente_nome": "ANA",
        "usuario_id": 1,
        "usuario_nome": "Joana",
        "forma_pagamento": "DINHEIRO",
        "forma_pagamento_2": None,
        "valor_total": 30.0,
        "status": "FINALIZADA",
        "itens": [
            {"id": 11, "produto_id": 5, "produto_nome": "Blusa", "quantidade": 2,
             "valor_unitario": 20.0, "subtotal": 40.0},
        ],
    }
    venda.update(extra)
    return venda


# ==================================================
# DevolucaoDialog
# ==================================================


def test_fator_desconto_rateia_o_desconto():
    # itens somam 40, a venda saiu por 30
    assert fator_desconto(_venda()) == 0.75


def test_dialogo_calcula_valor_com_desconto_e_limita_ao_que_resta(_qapp):
    devolucoes = [{"itens": [{"item_venda_id": 11, "quantidade": 1}], "valor_total": 15}]
    dialogo = DevolucaoDialog(_venda(), devolucoes)

    assert dialogo.spins[0].maximum() == 1  # vendeu 2, já devolveu 1

    dialogo.spins[0].setValue(1)
    assert dialogo._total == 15.0


def test_abater_do_fiado_so_aparece_com_cliente(_qapp):
    com_cliente = DevolucaoDialog(_venda(), [])
    sem_cliente = DevolucaoDialog(_venda(cliente_id=None), [])

    assert com_cliente.forma.findData("PRAZO") >= 0
    assert sem_cliente.forma.findData("PRAZO") == -1


def test_venda_fiado_ja_sugere_abater_do_fiado(_qapp):
    dialogo = DevolucaoDialog(_venda(forma_pagamento="PRAZO"), [])
    assert dialogo.forma.currentData() == "PRAZO"


def test_trocar_agora_registra_em_dinheiro(_qapp, esperar_threads):
    dialogo = DevolucaoDialog(_venda(forma_pagamento="PRAZO"), [])
    dialogo.spins[0].setValue(1)

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
         mock.patch(
             "telas.devolucao_dialog.registrar_devolucao",
             return_value=_Resposta(200, {"valor_total": 15.0}),
         ) as registrar:
        dialogo.confirmar(troca=True)
        esperar_threads(dialogo)

    assert registrar.call_args.args[2] == "DINHEIRO"
    assert dialogo.troca is True
    assert dialogo.valor_devolvido == 15.0
    assert dialogo.result() == DevolucaoDialog.Accepted


def test_so_devolver_usa_a_forma_escolhida(_qapp, esperar_threads):
    dialogo = DevolucaoDialog(_venda(), [])
    dialogo.spins[0].setValue(2)
    dialogo.forma.setCurrentIndex(dialogo.forma.findData("PIX"))

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
         mock.patch(
             "telas.devolucao_dialog.registrar_devolucao",
             return_value=_Resposta(200, {"valor_total": 30.0}),
         ) as registrar:
        dialogo.confirmar(troca=False)
        esperar_threads(dialogo)

    assert registrar.call_args.args[1] == [{"item_venda_id": 11, "quantidade": 2}]
    assert registrar.call_args.args[2] == "PIX"
    assert dialogo.troca is False


def test_erro_do_servidor_mantem_a_janela_aberta(_qapp, esperar_threads):
    dialogo = DevolucaoDialog(_venda(), [])
    dialogo.show()
    dialogo.spins[0].setValue(1)

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
         mock.patch.object(QMessageBox, "warning") as aviso, \
         mock.patch(
             "telas.devolucao_dialog.registrar_devolucao",
             return_value=_Resposta(400, {"detail": "Não existe caixa aberto."}),
         ):
        dialogo.confirmar(troca=False)
        esperar_threads(dialogo)

    assert "caixa aberto" in aviso.call_args.args[2]
    assert dialogo.isVisible()
    dialogo.reject()


# ==================================================
# Tela de Vendas
# ==================================================


def _tela_vendas(monkeypatch):
    monkeypatch.setattr(api, "_INFO_USUARIO_CACHE", {"admin": True})
    return Vendas()


def test_tela_vendas_mostra_resumo_e_filtra_por_vendedora(_qapp, monkeypatch):
    tela = _tela_vendas(monkeypatch)

    vendas = [
        _venda(),
        _venda(id=8, usuario_id=2, usuario_nome="Bia", valor_total=50.0),
        _venda(id=9, status="ABERTA"),  # suspensa: não entra
    ]
    resumo = [
        {"usuario_id": 2, "usuario_nome": "Bia", "quantidade_vendas": 1,
         "total_vendido": 50, "total_devolvido": 0, "total_liquido": 50},
        {"usuario_id": 1, "usuario_nome": "Joana", "quantidade_vendas": 1,
         "total_vendido": 30, "total_devolvido": 15, "total_liquido": 15},
    ]

    tela._ao_carregar((vendas, resumo))

    assert tela.tabela.rowCount() == 2
    assert tela.tabela_vendedoras.rowCount() == 2
    assert tela.card_total.lbl_valor.text() == "R$ 65,00"
    assert tela.card_devolvido.lbl_valor.text() == "R$ 15,00"

    tela.filtro_vendedora.setCurrentIndex(tela.filtro_vendedora.findData(2))
    assert tela.tabela.rowCount() == 1
    assert tela.tabela.item(0, 3).text() == "Bia"


def test_venda_com_devolucao_nao_pode_ser_cancelada(_qapp, monkeypatch):
    tela = _tela_vendas(monkeypatch)
    venda = _venda()
    tela.vendas = [venda]

    tela.venda_atual = venda
    tela.devolucoes_atual = []
    tela._mostrar_detalhe(venda)
    assert tela.bt_cancelar.isEnabled()
    assert tela.bt_devolver.isEnabled()

    tela.devolucoes_atual = [{"itens": [{"item_venda_id": 11, "quantidade": 2}], "valor_total": 30}]
    tela._mostrar_detalhe(venda)
    assert not tela.bt_cancelar.isEnabled()
    assert not tela.bt_devolver.isEnabled()  # já voltou tudo


def test_venda_cancelada_nao_tem_acoes(_qapp, monkeypatch):
    tela = _tela_vendas(monkeypatch)
    venda = _venda(status="CANCELADA")
    tela.devolucoes_atual = []
    tela._mostrar_detalhe(venda)
    assert not tela.bt_cancelar.isEnabled()
    assert not tela.bt_devolver.isEnabled()


def test_botoes_escondidos_sem_permissao(_qapp, monkeypatch):
    monkeypatch.setattr(api, "_INFO_USUARIO_CACHE", {"admin": False, "permissoes": []})
    tela = Vendas()
    assert tela.bt_cancelar.isHidden()
    assert tela.bt_devolver.isHidden()


# ==================================================
# Crédito de troca no PDV / pagamento
# ==================================================


def test_pagamento_ja_lanca_o_credito_da_troca_em_dinheiro(_qapp):
    tela = PagamentoWindow(50.0, [{"preco": 50.0, "quantidade": 1}], credito_troca=30.0)

    assert tela.pagamentos == [{"forma": "DINHEIRO", "valor": 30.0, "entregue": 30.0}]
    assert round(tela.falta(), 2) == 20.0


def test_credito_maior_que_a_venda_quita_tudo(_qapp):
    tela = PagamentoWindow(20.0, [{"preco": 20.0, "quantidade": 1}], credito_troca=30.0)

    assert tela.pagamentos[0]["valor"] == 20.0
    assert tela.quitado()


def test_pdv_iniciar_troca_guarda_credito_e_cliente(_qapp):
    pdv = _tela_pdv()

    pdv.iniciar_troca(30.0, {"id": 3, "nome": "ANA"})

    assert pdv.credito_troca == 30.0
    assert pdv.cliente_id == 3
    assert not pdv.badge_troca.isHidden()


def test_cancelar_carrinho_vazio_tira_o_credito_da_troca(_qapp):
    pdv = _tela_pdv()
    pdv.iniciar_troca(30.0)

    with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
         mock.patch.object(QMessageBox, "information") as aviso:
        pdv.cancelar_venda()

    assert pdv.credito_troca == 0.0
    assert pdv.badge_troca.isHidden()
    assert "R$ 30,00" in aviso.call_args.args[2]
