"""Imprimir da tela Vendas: lista as vendas com os itens e soma por forma,
na janela do Windows (HTML) e na termica de 80mm."""
from services.impressora_termica_service import gerar_comandos_vendas
from telas.vendas import Vendas


def _venda(id_, forma, total, itens, status="FINALIZADA", observacao=None):
    return {
        "id": id_, "data": "2026-10-10T09:39:00", "cliente_nome": "MARY (BABA)",
        "usuario_nome": "ANDRE", "usuario_id": 1, "forma_pagamento": forma,
        "valor_total": total, "status": status, "itens": itens, "observacao": observacao,
    }


def _relatorio():
    return Vendas()._dados_relatorio([
        _venda(30, "DINHEIRO", "50.00", [
            {"id": 1, "produto_id": 7, "produto_nome": "CARTUCHO", "quantidade": 5, "subtotal": "50.00"},
        ]),
        _venda(33, "PRAZO", "68.99", [], observacao="1x KIT BEBE"),
        _venda(34, "PIX", "100.00", [], status="CANCELADA"),
    ])


def test_relatorio_tem_itens_e_total_sem_canceladas(_qapp):
    relatorio = _relatorio()
    html = Vendas()._html_relatorio(relatorio)

    assert relatorio["quantidade"] == 2
    assert relatorio["total"] == 118.99
    assert "5x CARTUCHO" in html
    assert "1x KIT BEBE" in html
    assert "(CANCELADA)" in html
    assert "R$ 118,99" in html


def test_cupom_80mm_tem_itens_e_total(_qapp):
    comandos = gerar_comandos_vendas(_relatorio(), {"nome_loja": "3.L.A VARIEDADES"}, 80)
    texto = comandos.decode("cp860", "ignore")

    assert "5x CARTUCHO" in texto
    assert "1x KIT BEBE" in texto
    assert "CANCELADA" in texto
    assert "TOTAL (2 vendas)" in texto


def test_botao_imprimir_manda_pra_termica(_qapp, esperar_threads, monkeypatch):
    from services import api, impressora_termica_service, preferencias_service

    tela = Vendas()
    tela.vendas = [_venda(30, "DINHEIRO", "50.00", [])]
    config = {"ativa": True, "tipo": "usb", "nome_impressora_windows": "Generic / Text Only", "largura_papel": 80}
    monkeypatch.setattr(preferencias_service, "carregar_impressora_termica", lambda: config)
    monkeypatch.setattr(api, "configuracoes", lambda: {"nome_loja": "3.L.A VARIEDADES"})
    enviados = []
    monkeypatch.setattr(
        impressora_termica_service, "enviar",
        lambda dados, cfg: enviados.append((dados, cfg)) or (True, None),
    )

    tela.imprimir()
    esperar_threads(tela)

    [(dados, cfg)] = enviados
    assert cfg is config
    assert b"3.L.A VARIEDADES" in dados
