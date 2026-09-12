"""Testes de services/impressora_termica_service.py -- geração dos
comandos ESC/POS (texto, imagem, cupom completo) e envio (rede/USB
mockados, sem precisar de impressora de verdade). Ver a decisão desse
serviço existir em impressora_termica_service.py: impressora térmica
genérica instalada com driver "Generic / Text Only" não sabe desenhar
gráfico nenhum, então em vez de depender do QPrinter/driver do
Windows, manda os bytes ESC/POS direto."""
import socket
from io import BytesIO
from unittest import mock

from services import impressora_termica_service as svc


def test_codificar_texto_sem_acento():
    assert svc._codificar_texto("Nao tem acento") == b"Nao tem acento"


def test_codificar_texto_com_acentos_comuns():
    b = svc._codificar_texto("Endereço, telefone, código, ação")
    assert isinstance(b, bytes) and len(b) > 0
    assert "ç".encode("cp860") in b


def test_codificar_texto_fora_da_pagina_de_codigo_nao_trava():
    b = svc._codificar_texto("emoji 🎉 no meio")
    assert isinstance(b, bytes)
    assert b"emoji" in b and b"no meio" in b


def test_linha_dupla_coluna_cabendo_vira_uma_linha():
    linha = svc._linha_dupla_coluna("TOTAL", "R$ 50,00", 20)
    assert linha.count(b"\n") == 1
    assert len(linha.rstrip(b"\n")) == 20


def test_linha_dupla_coluna_estourando_quebra_em_duas():
    linha = svc._linha_dupla_coluna(
        "Produto com nome bem comprido demais", "R$ 5,00", 20
    )
    assert linha.count(b"\n") == 2


def test_divisoria_tem_o_tamanho_certo():
    assert len(svc._divisoria(32).rstrip(b"\n")) == 32


def test_largura_do_papel_80mm():
    assert svc._colunas(80) == 48
    assert svc._pontos(80) == 576


def test_largura_do_papel_58mm():
    assert svc._colunas(58) == 32
    assert svc._pontos(58) == 384


def test_largura_desconhecida_cai_pro_padrao_80mm():
    assert svc._colunas(999) == 48


def test_comando_de_imagem():
    from PIL import Image

    img = Image.new("L", (16, 8), color=255)
    for x in range(8):
        for y in range(8):
            img.putpixel((x, y), 0)  # metade esquerda preta

    buffer = BytesIO()
    img.save(buffer, format="PNG")

    comando = svc._comando_imagem(buffer.getvalue(), 16)

    largura_bytes = (16 + 7) // 8
    assert comando[:3] == b"\x1dv0"
    assert comando[4] == largura_bytes and comando[5] == 0  # xL, xH
    assert comando[6] == 8 and comando[7] == 0  # yL, yH
    assert len(comando) == 8 + largura_bytes * 8


def test_comando_de_imagem_com_png_invalido_devolve_none():
    assert svc._comando_imagem(b"isso nao e um png", 16) is None


DADOS_VENDA = {
    "venda_id": 42,
    "data": "2026-09-09T14:30:00",
    "usuario_nome": "João",
    "cliente_nome": "Maria Souza",
    "cliente_cpf_cnpj": "123.456.789-00",
    "itens": [
        {"nome": "Produto A", "quantidade": 2, "valor_unitario": 10.0, "subtotal": 20.0},
        {
            "nome": "Produto com nome bem comprido pra testar quebra de linha",
            "quantidade": 1,
            "valor_unitario": 5.5,
            "subtotal": 5.5,
        },
    ],
    "desconto": 2.5,
    "valor_total": 23.0,
    "forma_pagamento": "PIX",
    "situacao": "PAGO",
    "observacao": "Entregar embrulhado",
}

CONFIG_LOJA = {
    "nome_loja": "Loja Teste",
    "endereco": "Rua Um, 123",
    "telefone": "(11) 99999-0000",
    "cnpj_cpf": "00.000.000/0001-00",
}


def test_cupom_de_venda_completo():
    comandos = svc.gerar_comandos_comprovante(DADOS_VENDA, CONFIG_LOJA)

    assert comandos.startswith(svc._INICIALIZAR)
    assert comandos.endswith(svc._cortar_papel())
    assert svc._codificar_texto("Loja Teste") in comandos
    assert svc._codificar_texto("Pedido nº: 42") in comandos
    assert svc._codificar_texto("R$ 23.00") in comandos
    assert b"PIX" in comandos
    assert svc._codificar_texto("Maria Souza") in comandos
    assert svc._codificar_texto("Entregar embrulhado") in comandos


def test_cupom_fiado_mostra_saldo_devedor():
    comandos = svc.gerar_comandos_comprovante(
        {**DADOS_VENDA, "situacao": "FIADO", "saldo_devedor_cliente": 150.0},
        CONFIG_LOJA,
    )
    assert svc._codificar_texto("EM ABERTO") in comandos
    assert svc._codificar_texto("R$ 150.00") in comandos


def test_cupom_58mm_gera_sem_erro():
    comandos = svc.gerar_comandos_comprovante(DADOS_VENDA, CONFIG_LOJA, largura_papel_mm=58)
    assert len(comandos) > 0


def test_recibo_de_teste():
    comandos = svc.gerar_comandos_teste(80)
    assert b"VERTEX ERP" in comandos
    assert b"80mm" in comandos


CLIENTE = {"nome": "Carlos Lima", "cpf_cnpj": "111.222.333-44", "telefone": "(11) 98888-0000"}
MOVIMENTOS = [
    {"data": "2026-09-01 10:00", "descricao": "Compra: Produto X", "tipo": "COMPRA", "valor": 30.0, "saldo_apos": 30.0},
    {"data": "2026-09-05 15:00", "descricao": "Pagamento em dinheiro", "tipo": "PAGAMENTO", "valor": 10.0, "saldo_apos": 20.0},
]
OBSERVACOES = [{"criado_em": "2026-09-02T00:00:00", "texto": "Cliente pediu prazo"}]


def test_extrato_do_cliente():
    comandos = svc.gerar_comandos_extrato(
        CLIENTE, MOVIMENTOS, OBSERVACOES, saldo=20.0, responsavel="Ana",
        config_loja=CONFIG_LOJA, largura_papel_mm=80,
    )
    assert svc._codificar_texto("Carlos Lima") in comandos
    assert svc._codificar_texto("R$ 20.00") in comandos
    assert svc._codificar_texto("Ana") in comandos
    assert svc._codificar_texto("Cliente pediu prazo") in comandos
    assert comandos.endswith(svc._cortar_papel())


def test_extrato_sem_movimentacao_nao_trava():
    comandos = svc.gerar_comandos_extrato(
        CLIENTE, [], [], saldo=0.0, responsavel="Ana", config_loja=CONFIG_LOJA,
    )
    assert svc._codificar_texto("Nenhuma movimentacao registrada.") in comandos


def test_recibo_pagamento_quitado():
    comandos = svc.gerar_comandos_recibo_pagamento(
        cliente_nome="Carlos Lima", valor=20.0, forma_pagamento="PIX",
        saldo_antes=20.0, saldo_depois=0.0, responsavel="Ana",
        momento="2026-09-10T14:30:00", config_loja=CONFIG_LOJA,
    )
    assert svc._codificar_texto("RECIBO DE PAGAMENTO") in comandos
    assert svc._codificar_texto("Carlos Lima") in comandos
    assert svc._codificar_texto("Ana") in comandos
    assert svc._codificar_texto("R$ 20.00") in comandos
    assert svc._codificar_texto("QUITADO") in comandos
    assert comandos.endswith(svc._cortar_papel())


def test_recibo_pagamento_saldo_em_aberto():
    comandos = svc.gerar_comandos_recibo_pagamento(
        cliente_nome="Carlos Lima", valor=20.0, forma_pagamento="DINHEIRO",
        saldo_antes=50.0, saldo_depois=30.0, responsavel="Ana",
        momento="2026-09-10T14:30:00", config_loja=CONFIG_LOJA,
    )
    assert svc._codificar_texto("SALDO EM ABERTO") in comandos
    assert svc._codificar_texto("R$ 30.00") in comandos
    assert svc._codificar_texto("R$ 50.00") in comandos


def test_recibo_pagamento_58mm_gera_sem_erro():
    comandos = svc.gerar_comandos_recibo_pagamento(
        cliente_nome="Carlos Lima", valor=20.0, forma_pagamento="PIX",
        saldo_antes=20.0, saldo_depois=0.0, responsavel="Ana",
        momento="2026-09-10T14:30:00", config_loja=CONFIG_LOJA,
        largura_papel_mm=58,
    )
    assert len(comandos) > 0


def test_enviar_por_rede_com_sucesso():
    with mock.patch("socket.create_connection") as mock_conexao:
        mock_socket = mock.MagicMock()
        mock_conexao.return_value.__enter__.return_value = mock_socket

        ok, erro = svc.enviar(
            b"dados de teste", {"tipo": "rede", "ip": "192.168.0.50", "porta": 9100}
        )

        assert ok is True and erro is None
        assert mock_conexao.call_args[0][0] == ("192.168.0.50", 9100)
        assert mock_socket.sendall.call_args[0][0] == b"dados de teste"


def test_enviar_por_rede_sem_ip_da_erro_amigavel():
    ok, erro = svc.enviar(b"x", {"tipo": "rede", "ip": None, "porta": 9100})
    assert ok is False and "IP" in erro


def test_enviar_por_rede_timeout_vira_mensagem_amigavel():
    with mock.patch("socket.create_connection", side_effect=socket.timeout("timed out")):
        ok, erro = svc.enviar(b"x", {"tipo": "rede", "ip": "10.0.0.1", "porta": 9100})
        assert ok is False and "tempo esgotado" in erro


def test_enviar_por_rede_conexao_recusada_vira_mensagem_amigavel():
    with mock.patch("socket.create_connection", side_effect=ConnectionRefusedError("refused")):
        ok, erro = svc.enviar(b"x", {"tipo": "rede", "ip": "10.0.0.1", "porta": 9100})
        assert ok is False and "recusou" in erro


def test_enviar_sem_tipo_configurado_da_erro_amigavel():
    ok, erro = svc.enviar(b"x", {"tipo": None})
    assert ok is False and "Configure" in erro


def test_enviar_por_usb_com_sucesso():
    win32print_falso = mock.MagicMock()
    win32print_falso.OpenPrinter.return_value = "handle-fake"

    with mock.patch.dict("sys.modules", {"win32print": win32print_falso}):
        ok, erro = svc.enviar(
            b"dados usb", {"tipo": "usb", "nome_impressora_windows": "Minha Impressora"}
        )

        assert ok is True and erro is None
        assert win32print_falso.OpenPrinter.call_args[0][0] == "Minha Impressora"
        # datatype RAW -- nao passa pelo driver grafico
        assert win32print_falso.StartDocPrinter.call_args[0][2][2] == "RAW"
        assert win32print_falso.WritePrinter.call_args[0][1] == b"dados usb"
        assert win32print_falso.ClosePrinter.called


def test_enviar_por_usb_sem_impressora_escolhida_da_erro_amigavel():
    ok, erro = svc.enviar(b"x", {"tipo": "usb", "nome_impressora_windows": None})
    assert ok is False and "Escolha" in erro


def test_listar_impressoras_windows():
    win32print_falso = mock.MagicMock()
    win32print_falso.EnumPrinters.return_value = [
        (0, "", "Impressora B", ""),
        (0, "", "Impressora A", ""),
    ]

    with mock.patch.dict("sys.modules", {"win32print": win32print_falso}):
        assert svc.listar_impressoras_windows() == ["Impressora A", "Impressora B"]
