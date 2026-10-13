"""Testes do dialogo de importacao em massa de produtos via CSV
(Fase 6, Onda 9) -- chama os metodos de preview/confirmar direto
(sem passar pelo QFileDialog de verdade, que exige interacao)."""
from unittest import mock

from telas.importar_produtos_csv import ImportarProdutosCsvDialog, ler_texto_csv

PREVIEW_OK = {
    "itens": [
        {
            "linha": 2, "codigo": "PROD-1", "nome": "Camiseta",
            "categoria": "Roupa", "codigo_barras": None,
            "preco_custo": "10.00", "preco_venda": "20.00",
            "estoque": 5, "estoque_minimo": 1, "unidade": "UN",
            "produto_id": None, "erro": None,
        },
        {
            "linha": 3, "codigo": "PROD-2", "nome": "Existente",
            "categoria": "Roupa", "codigo_barras": None,
            "preco_custo": "5.00", "preco_venda": "10.00",
            "estoque": 2, "estoque_minimo": 0, "unidade": "UN",
            "produto_id": 99, "erro": None,
        },
        {
            "linha": 4, "codigo": "PROD-3", "nome": "",
            "categoria": None, "codigo_barras": None,
            "preco_custo": "0", "preco_venda": "0",
            "estoque": 0, "estoque_minimo": 0, "unidade": "UN",
            "produto_id": None, "erro": "nome vazio",
        },
    ],
    "total_novos": 1,
    "total_atualizados": 1,
    "total_com_erro": 1,
}


def test_preview_popula_tabela_e_habilita_confirmar_so_com_validos():
    dialogo = ImportarProdutosCsvDialog()

    dialogo._ao_preview_sucesso(PREVIEW_OK)

    assert dialogo.paginas.currentWidget() is dialogo.pagina_preview
    assert dialogo.tabela_preview.rowCount() == 3
    assert dialogo.bt_confirmar.isEnabled() is True
    assert "2" in dialogo.bt_confirmar.text()  # 2 validos (novo + atualiza)


def test_preview_vazio_nao_troca_de_pagina():
    dialogo = ImportarProdutosCsvDialog()

    with mock.patch(
        "telas.importar_produtos_csv.Mensagem.aviso"
    ) as aviso_mock:
        dialogo._ao_preview_sucesso({
            "itens": [], "total_novos": 0, "total_atualizados": 0,
            "total_com_erro": 0,
        })

    aviso_mock.assert_called_once()
    assert dialogo.paginas.currentWidget() is dialogo.pagina_selecao


def test_confirmar_manda_so_os_itens_sem_erro(esperar_threads):
    dialogo = ImportarProdutosCsvDialog()
    dialogo._ao_preview_sucesso(PREVIEW_OK)

    with mock.patch(
        "telas.importar_produtos_csv.importar_csv_confirmar",
        return_value={"criados": 1, "atualizados": 1},
    ) as confirmar_mock, mock.patch(
        "telas.importar_produtos_csv.Mensagem.sucesso"
    ), mock.patch.object(dialogo, "accept") as accept_mock:

        sinal_recebido = []
        dialogo.importado.connect(lambda: sinal_recebido.append(True))

        dialogo._confirmar()
        esperar_threads(dialogo)

    itens_enviados = confirmar_mock.call_args[0][0]
    assert len(itens_enviados) == 2
    assert all(item["erro"] is None for item in itens_enviados)
    assert sinal_recebido == [True]
    accept_mock.assert_called_once()


def test_ler_csv_aceita_utf8_e_ansi_do_excel():
    texto = "Nome;Categoria\r\nTÊNIS;CALÇADOS\r\n"
    assert ler_texto_csv(texto.encode("utf-8-sig")) == texto
    assert ler_texto_csv(texto.encode("cp1252")) == texto
