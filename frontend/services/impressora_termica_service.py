"""Impressão direta em impressora térmica de cupom (ESC/POS), sem passar
pelo sistema de impressão gráfica do Windows.

Por quê: o comprovante normal (ver comprovante_service.py) é desenhado
como HTML/gráfico e mandado pro driver da impressora via QPrinter --
isso funciona bem em impressora normal (A4/A5), mas várias impressoras
térmicas baratas/genéricas (o tipo mais comum vendido pra PDV pequeno)
vêm instaladas no Windows com um driver "Generic / Text Only" que não
sabe desenhar gráficos, só processar texto puro -- o resultado é a
impressora reagir (avança papel) mas nada aparecer no cupom, porque o
driver não consegue interpretar o documento gráfico que o Qt manda.

A solução aqui é não depender do driver gráfico nenhum: monta o cupom
como uma sequência de comandos ESC/POS (o "protocolo" que praticamente
toda impressora térmica de recibo entende, driver bom ou ruim) e manda
esses bytes direto pro dispositivo -- por rede (a maioria dessas
impressoras tem porta LAN, e a porta 9100 é o padrão universal de
"impressão crua" que qualquer impressora de rede aceita) ou por USB via
modo RAW do spooler do Windows (que também ignora completamente a
capacidade gráfica do driver instalado -- só repassa os bytes pro
dispositivo, então funciona mesmo com o driver genérico).
"""

import textwrap
import unicodedata
from datetime import datetime
from io import BytesIO
from urllib.parse import quote

# ==================================================
# COMANDOS ESC/POS
# ==================================================

_ESC = b"\x1b"
_GS = b"\x1d"

_INICIALIZAR = _ESC + b"\x40"  # ESC @ -- reseta o estado da impressora

# ESC t 3 -- seleciona a página de código PC860 (Português), padrão
# Epson replicado pela imensa maioria dos clones ESC/POS
_SELECIONAR_PAGINA_CODIGO = _ESC + b"\x74\x03"


def _alinhar(modo):
    """modo: 0 = esquerda, 1 = centro, 2 = direita (ESC a n)."""
    return _ESC + b"\x61" + bytes([modo])


def _negrito(ligado):
    return _ESC + b"\x45" + bytes([1 if ligado else 0])


def _tamanho_fonte(largura=1, altura=1):
    """GS ! n -- largura/altura de 1 (normal) a 8 (8x maior)."""
    n = ((largura - 1) & 0x07) << 4 | ((altura - 1) & 0x07)
    return _GS + b"\x21" + bytes([n])


def _avancar_linhas(quantidade):
    return _ESC + b"\x64" + bytes([quantidade])


def _cortar_papel():
    # avança um pouco antes de cortar, senão o corte cai em cima do
    # texto (o cabeçote de corte fica alguns milímetros à frente do
    # que já foi impresso)
    return _avancar_linhas(4) + _GS + b"\x56\x01"


# ==================================================
# LARGURA DO PAPEL
# ==================================================

_COLUNAS_POR_LARGURA = {58: 32, 80: 48}
_PONTOS_POR_LARGURA = {58: 384, 80: 576}


def _colunas(largura_papel_mm):
    return _COLUNAS_POR_LARGURA.get(largura_papel_mm, 48)


def _pontos(largura_papel_mm):
    return _PONTOS_POR_LARGURA.get(largura_papel_mm, 576)


# ==================================================
# TEXTO
# ==================================================


def _codificar_texto(texto):
    """Converte pra bytes usando PC860 (acompanha o ESC t 3 acima) --
    se algum caractere não existir nessa página de código (raro, mas
    alguns clones não implementam a tabela completa), cai pra uma
    versão sem acento em vez de arriscar imprimir lixo."""

    partes = []

    for caractere in texto:
        try:
            partes.append(caractere.encode("cp860"))
        except UnicodeEncodeError:
            sem_acento = unicodedata.normalize(
                "NFKD", caractere
            ).encode("ascii", "ignore")
            partes.append(sem_acento or b"?")

    return b"".join(partes)


def _linha(texto=""):
    return _codificar_texto(texto) + b"\n"


def _linha_dupla_coluna(esquerda, direita, largura):
    """Uma linha com um texto colado à esquerda e outro à direita (ex:
    'TOTAL' ... 'R$ 50,00') -- se não couber os dois na mesma linha,
    quebra em duas em vez de embaralhar a coluna."""

    espaco = largura - len(esquerda) - len(direita)

    if espaco < 1:
        return _linha(esquerda) + _linha(direita.rjust(largura))

    return _linha(f"{esquerda}{' ' * espaco}{direita}")


def _linhas_quebradas(texto, largura):
    linhas = textwrap.wrap(texto, largura) or [""]
    return b"".join(_linha(linha) for linha in linhas)


def _divisoria(largura):
    return _linha("-" * largura)


def _moeda(valor):
    return f"R$ {float(valor or 0):.2f}"


def _data(data_iso):
    if not data_iso:
        return "-"
    texto = str(data_iso).replace("T", " ")
    return texto[:16]


def _data_com_hora(data_iso):
    """"YYYY-MM-DDTHH:MM..." -> "DD/MM/AAAA às HH:MM" -- formato usado
    nos comprovantes/recibos impressos (ver pedido do usuário)."""

    if not data_iso:
        return "—"

    texto = str(data_iso).replace("T", " ")[:16]

    try:
        dt = datetime.strptime(texto, "%Y-%m-%d %H:%M")
        return dt.strftime("%d/%m/%Y às %H:%M")
    except ValueError:
        return texto


# ==================================================
# IMAGEM (raster) -- usado pro logo da loja e pro QR Code, reaproveita
# os mesmos PNGs já gerados pro comprovante em HTML
# ==================================================


def _comando_imagem(imagem_bytes, largura_pontos_alvo):
    """Converte um PNG em preto-e-branco pro comando ESC/POS de
    impressão de imagem raster (GS v 0) -- devolve None se a imagem
    vier corrompida/em formato que o Pillow não abra, pra quem chamar
    decidir simplesmente pular esse bloco em vez de travar o cupom
    inteiro por causa de uma imagem."""

    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        imagem = Image.open(BytesIO(imagem_bytes)).convert("L")
    except Exception:
        return None

    if imagem.width == 0 or imagem.height == 0:
        return None

    proporcao = largura_pontos_alvo / imagem.width
    altura_pontos = max(1, round(imagem.height * proporcao))
    imagem = imagem.resize((largura_pontos_alvo, altura_pontos))

    pixels = imagem.load()
    largura_bytes = (largura_pontos_alvo + 7) // 8

    linhas_bits = bytearray(largura_bytes * altura_pontos)

    for y in range(altura_pontos):
        offset_linha = y * largura_bytes
        for x in range(largura_pontos_alvo):
            if pixels[x, y] < 128:  # mais escuro que cinza médio -> pixel preto
                linhas_bits[offset_linha + x // 8] |= 0x80 >> (x % 8)

    x_l = largura_bytes & 0xFF
    x_h = (largura_bytes >> 8) & 0xFF
    y_l = altura_pontos & 0xFF
    y_h = (altura_pontos >> 8) & 0xFF

    return (
        _GS + b"v0" + bytes([0, x_l, x_h, y_l, y_h]) + bytes(linhas_bits)
    )


def _gerar_qrcode_png(texto):
    import qrcode

    qr = qrcode.QRCode(box_size=3, border=2)
    qr.add_data(texto)
    qr.make(fit=True)

    buffer = BytesIO()
    qr.make_image().save(buffer, format="PNG")

    return buffer.getvalue()


def _comando_qr_whatsapp(nome_loja, telefone_loja, pontos):
    """QR code que abre direto uma conversa no WhatsApp da loja com uma
    mensagem pronta -- em vez de só codificar um texto solto que não
    leva a lugar nenhum quando escaneado. Sem telefone configurado não
    tem como montar o link, então não desenha QR nenhum (melhor não
    mostrar do que mostrar um QR que não funciona)."""

    if not telefone_loja:
        return None

    digitos = "".join(c for c in telefone_loja if c.isdigit())

    if not digitos:
        return None

    if len(digitos) <= 11:
        digitos = "55" + digitos

    mensagem = f"Olá! Vim pelo comprovante da {nome_loja} e preciso de atendimento."
    link = f"https://wa.me/{digitos}?text={quote(mensagem)}"

    return _comando_imagem(_gerar_qrcode_png(link), pontos // 3)


# ==================================================
# FECHAMENTO DE CAIXA -- rotulos de tipo de movimento em texto puro
# (mesma ideia da pill colorida da tela, sem cor no cupom termico)
# ==================================================

_ROTULOS_TIPO_MOVIMENTO = {
    "VENDA": "Venda",
    "SUPRIMENTO": "Suprimento",
    "SANGRIA": "Sangria",
    "RECEBIMENTO_FIADO": "Receb. fiado",
    "ESTORNO": "Estorno",
}


# ==================================================
# CUPOM DE VENDA (comprovante)
# ==================================================


def gerar_comandos_comprovante(dados, config_loja, logo_bytes=None, largura_papel_mm=80):

    largura = _colunas(largura_papel_mm)
    pontos = _pontos(largura_papel_mm)

    partes = [_INICIALIZAR, _SELECIONAR_PAGINA_CODIGO]

    partes.append(_alinhar(1))  # centro

    if logo_bytes:
        comando_logo = _comando_imagem(logo_bytes, min(pontos, pontos * 2 // 3))
        if comando_logo:
            partes.append(comando_logo)
            partes.append(_linha())

    nome_loja = config_loja.get("nome_loja") or "Vertex ERP"
    telefone_loja = config_loja.get("telefone")

    partes.append(_negrito(True))
    partes.append(_tamanho_fonte(2, 2))
    partes.append(_linha(nome_loja))
    partes.append(_tamanho_fonte(1, 1))
    partes.append(_negrito(False))

    if config_loja.get("endereco"):
        partes.append(_linhas_quebradas(config_loja["endereco"], largura))
    if telefone_loja:
        partes.append(_linha(f"WhatsApp: {telefone_loja}"))
    if config_loja.get("cnpj_cpf"):
        partes.append(_linha(f"CNPJ: {config_loja['cnpj_cpf']}"))

    partes.append(_divisoria(largura))

    partes.append(_negrito(True))
    partes.append(_linha("COMPROVANTE DE VENDA"))
    partes.append(_negrito(False))

    partes.append(_divisoria(largura))
    partes.append(_alinhar(0))  # esquerda

    partes.append(_linha(f"Pedido nº: {dados['venda_id']}"))
    partes.append(_linha(f"Data: {_data_com_hora(dados.get('data'))}"))

    if dados.get("usuario_nome"):
        partes.append(_linha(f"Atendente: {dados['usuario_nome']}"))

    if dados.get("cliente_nome"):
        partes.append(_linha(f"Cliente: {dados['cliente_nome']}"))
        if dados.get("cliente_cpf_cnpj"):
            partes.append(_linha(f"CPF/CNPJ: {dados['cliente_cpf_cnpj']}"))

    partes.append(_divisoria(largura))

    partes.append(_negrito(True))
    partes.append(_linha("ITENS"))
    partes.append(_negrito(False))
    partes.append(_linha())

    for item in dados["itens"]:
        linha_item = f"{item['quantidade']}x  {item['nome']}"
        partes.append(
            _linha_dupla_coluna(linha_item, _moeda(item["subtotal"]), largura)
        )

    partes.append(_divisoria(largura))

    desconto = float(dados.get("desconto") or 0)
    if desconto > 0:
        partes.append(_linha_dupla_coluna("Desconto", f"-{_moeda(desconto)}", largura))
    elif desconto < 0:
        partes.append(_linha_dupla_coluna("Acréscimo", f"+{_moeda(-desconto)}", largura))

    partes.append(_negrito(True))
    partes.append(_tamanho_fonte(1, 2))
    partes.append(
        _linha_dupla_coluna("TOTAL DA COMPRA", _moeda(dados["valor_total"]), largura)
    )
    partes.append(_tamanho_fonte(1, 1))
    partes.append(_negrito(False))
    partes.append(_linha())

    if dados.get("forma_pagamento_2"):
        valor_principal = float(dados["valor_total"]) - float(
            dados.get("valor_forma_2") or 0
        )
        partes.append(
            _linha(f"Forma de pagamento: {_moeda(valor_principal)} ({dados['forma_pagamento']})")
        )
        partes.append(
            _linha(f"          + {_moeda(dados['valor_forma_2'])} ({dados['forma_pagamento_2']})")
        )
    else:
        partes.append(_linha(f"Forma de pagamento: {dados['forma_pagamento']}"))

    situacao = dados.get("situacao") or "PAGO"
    partes.append(_linha(f"Situação: {'EM ABERTO' if situacao == 'FIADO' else 'PAGO'}"))

    if situacao == "FIADO" and dados.get("saldo_devedor_cliente") is not None:
        partes.append(
            _linha_dupla_coluna(
                "Saldo pendente:", _moeda(dados["saldo_devedor_cliente"]), largura
            )
        )

    if dados.get("observacao"):
        partes.append(_divisoria(largura))
        partes.append(_linhas_quebradas(f"Obs: {dados['observacao']}", largura))

    partes.append(_divisoria(largura))
    partes.append(_alinhar(1))  # centro

    partes.append(_linha("Obrigado pela preferência!"))
    partes.append(_linha())

    comando_qr = _comando_qr_whatsapp(nome_loja, telefone_loja, pontos)
    if comando_qr:
        partes.append(comando_qr)
        partes.append(_linha())
        partes.append(_linha("Aponte a câmera para falar conosco."))
        partes.append(_linha())

    partes.append(_linha("Este comprovante não possui valor fiscal."))

    partes.append(_cortar_papel())

    return b"".join(partes)


# ==================================================
# RECIBO DE PAGAMENTO -- impresso ao registrar um pagamento de fiado
# na ficha do cliente (ver telas/ficha_cliente.py,
# RegistrarPagamentoDialog.confirmar).
# ==================================================


def gerar_comandos_recibo_pagamento(
    cliente_nome, valor, forma_pagamento, saldo_antes, saldo_depois,
    responsavel, momento, config_loja, largura_papel_mm=80,
):

    largura = _colunas(largura_papel_mm)
    pontos = _pontos(largura_papel_mm)

    partes = [_INICIALIZAR, _SELECIONAR_PAGINA_CODIGO]

    partes.append(_alinhar(1))

    nome_loja = config_loja.get("nome_loja") or "Vertex ERP"
    telefone_loja = config_loja.get("telefone")

    partes.append(_negrito(True))
    partes.append(_tamanho_fonte(2, 2))
    partes.append(_linha(nome_loja))
    partes.append(_tamanho_fonte(1, 1))
    partes.append(_negrito(False))

    if telefone_loja:
        partes.append(_linha(f"WhatsApp: {telefone_loja}"))

    partes.append(_divisoria(largura))

    partes.append(_negrito(True))
    partes.append(_linha("RECIBO DE PAGAMENTO"))
    partes.append(_negrito(False))

    partes.append(_divisoria(largura))
    partes.append(_alinhar(0))

    partes.append(_linha(f"Cliente: {cliente_nome}"))
    partes.append(_linha(f"Data: {_data_com_hora(momento)}"))
    partes.append(_linha(f"Atendente: {responsavel}"))

    partes.append(_divisoria(largura))

    partes.append(_negrito(True))
    partes.append(_linha("PAGAMENTO RECEBIDO"))
    partes.append(_negrito(False))
    partes.append(_linha())

    partes.append(_linha(f"Forma de pagamento: {forma_pagamento}"))
    partes.append(_linha_dupla_coluna("Valor recebido:", _moeda(valor), largura))

    partes.append(_divisoria(largura))

    partes.append(_negrito(True))
    partes.append(_linha("RESUMO DO CADASTRO"))
    partes.append(_negrito(False))
    partes.append(_linha())

    partes.append(
        _linha_dupla_coluna(
            "Saldo antes do pagamento:", _moeda(saldo_antes), largura
        )
    )
    partes.append(
        _linha_dupla_coluna(
            "Pagamento registrado:", f"-{_moeda(valor)}", largura
        )
    )
    partes.append(_linha())

    partes.append(_negrito(True))
    partes.append(
        _linha_dupla_coluna("Saldo atual:", _moeda(saldo_depois), largura)
    )
    partes.append(_negrito(False))
    partes.append(_linha())

    quitado = saldo_depois <= 0.009
    partes.append(_linha(f"Situação: {'QUITADO' if quitado else 'SALDO EM ABERTO'}"))

    partes.append(_divisoria(largura))
    partes.append(_alinhar(1))

    partes.append(_linha("Obrigado pelo pagamento e pela preferência!"))
    partes.append(_linha())

    comando_qr = _comando_qr_whatsapp(nome_loja, telefone_loja, pontos)
    if comando_qr:
        partes.append(comando_qr)
        partes.append(_linha())
        partes.append(_linha("Aponte a câmera para falar conosco."))
        partes.append(_linha())

    partes.append(_linha("Este comprovante não possui valor fiscal."))

    partes.append(_cortar_papel())

    return b"".join(partes)


# ==================================================
# EXTRATO DO CLIENTE
# ==================================================


def gerar_comandos_extrato(
    cliente, movimentos, observacoes, saldo, responsavel, config_loja,
    largura_papel_mm=80,
):
    """movimentos: lista de dicts já prontos pra exibição -- {"data",
    "descricao", "tipo" ("COMPRA"/"PAGAMENTO"), "valor", "saldo_apos"}
    -- quem chama monta essa lista reaproveitando a mesma descrição
    usada na tela (ver ficha_cliente.py, FichaCliente._descricao_com_itens),
    em vez desse módulo tentar reconstruir a regra sozinho."""

    largura = _colunas(largura_papel_mm)

    partes = [_INICIALIZAR, _SELECIONAR_PAGINA_CODIGO]

    partes.append(_alinhar(1))
    partes.append(_negrito(True))
    partes.append(_tamanho_fonte(2, 2))
    partes.append(_linha(config_loja.get("nome_loja") or "Vertex ERP"))
    partes.append(_tamanho_fonte(1, 1))
    partes.append(_negrito(False))

    if config_loja.get("telefone"):
        partes.append(_linha(config_loja["telefone"]))

    partes.append(_divisoria(largura))
    partes.append(_alinhar(0))

    partes.append(_negrito(True))
    partes.append(_linha("Extrato Financeiro"))
    partes.append(_negrito(False))
    partes.append(_linha(f"Cliente: {cliente.get('nome', '')}"))
    if cliente.get("cpf_cnpj"):
        partes.append(_linha(f"CPF/CNPJ: {cliente['cpf_cnpj']}"))
    if cliente.get("telefone"):
        partes.append(_linha(f"Telefone: {cliente['telefone']}"))

    partes.append(_divisoria(largura))

    if not movimentos:
        partes.append(_linha("Nenhuma movimentacao registrada."))

    for mov in movimentos:
        tipo = mov.get("tipo")
        valor = float(mov.get("valor", 0) or 0)

        partes.append(_linha(_data(mov.get("data"))))
        descricao = mov.get("descricao") or ("Compra" if tipo == "COMPRA" else "Pagamento")
        partes.append(_linhas_quebradas(f"  {descricao}", largura))

        rotulo_valor = f"  {'Debito' if tipo == 'COMPRA' else 'Credito'}: {_moeda(valor)}"
        partes.append(
            _linha_dupla_coluna(rotulo_valor, f"Saldo {_moeda(mov.get('saldo_apos'))}", largura)
        )

    if observacoes:
        partes.append(_divisoria(largura))
        partes.append(_negrito(True))
        partes.append(_linha("Observacoes"))
        partes.append(_negrito(False))
        for obs in observacoes:
            data_obs = str(obs.get("criado_em") or "")[:10]
            partes.append(_linhas_quebradas(f"{data_obs}: {obs.get('texto', '')}", largura))

    partes.append(_divisoria(largura))
    partes.append(_negrito(True))
    partes.append(_tamanho_fonte(1, 2))
    partes.append(_linha_dupla_coluna("TOTAL DEVEDOR", _moeda(saldo), largura))
    partes.append(_tamanho_fonte(1, 1))
    partes.append(_negrito(False))
    partes.append(_linha(f"Responsavel: {responsavel}"))

    partes.append(_cortar_papel())

    return b"".join(partes)


# ==================================================
# EXTRATO DE FECHAMENTO DE CAIXA -- impresso ao confirmar o
# fechamento do turno (ver telas/fechar_caixa.py), com o resumo por
# categoria (igual ao card da tela) e a lista crua de cada
# movimentação do dia, pra conferência posterior em papel.
# ==================================================


def gerar_comandos_fechamento_caixa(
    caixa, resumo, movimentos, valor_contado, observacoes, responsavel,
    fechado_em, config_loja, largura_papel_mm=80,
):

    largura = _colunas(largura_papel_mm)

    partes = [_INICIALIZAR, _SELECIONAR_PAGINA_CODIGO]

    partes.append(_alinhar(1))
    partes.append(_negrito(True))
    partes.append(_tamanho_fonte(2, 2))
    partes.append(_linha(config_loja.get("nome_loja") or "Vertex ERP"))
    partes.append(_tamanho_fonte(1, 1))
    partes.append(_negrito(False))

    if config_loja.get("telefone"):
        partes.append(_linha(config_loja["telefone"]))

    partes.append(_divisoria(largura))
    partes.append(_alinhar(0))

    partes.append(_negrito(True))
    partes.append(_linha("Extrato de Fechamento de Caixa"))
    partes.append(_negrito(False))
    partes.append(_linha(f"Aberto em: {_data(caixa.get('data_abertura'))}"))
    partes.append(_linha(f"Fechado em: {_data(fechado_em)}"))
    partes.append(_linha(f"Responsavel: {responsavel}"))

    partes.append(_divisoria(largura))
    partes.append(_negrito(True))
    partes.append(_linha("Resumo do Turno"))
    partes.append(_negrito(False))

    resumo_linhas = (
        ("Troco inicial", resumo.get("saldo_inicial", 0)),
        ("Vendas em dinheiro", resumo.get("vendas_dinheiro", 0)),
        ("Vendas PIX", resumo.get("vendas_pix", 0)),
        ("Vendas cartao", resumo.get("vendas_cartao", 0)),
        ("Vendas a prazo", resumo.get("vendas_prazo", 0)),
        ("Suprimentos", resumo.get("suprimentos", 0)),
        ("Sangrias", resumo.get("sangrias", 0)),
        ("Recebimentos fiado", resumo.get("recebimentos_fiado", 0)),
    )

    for rotulo, valor in resumo_linhas:
        partes.append(_linha_dupla_coluna(rotulo, _moeda(valor), largura))

    total_previsto = float(resumo.get("total_previsto", 0) or 0)

    partes.append(_divisoria(largura))
    partes.append(_negrito(True))
    partes.append(_linha_dupla_coluna("Total previsto", _moeda(total_previsto), largura))
    partes.append(_negrito(False))
    partes.append(
        _linha_dupla_coluna("Valor contado", _moeda(valor_contado), largura)
    )

    diferenca = float(valor_contado or 0) - total_previsto

    if abs(diferenca) < 0.01:
        texto_diferenca = "R$ 0,00 (confere)"
    elif diferenca > 0:
        texto_diferenca = f"+ {_moeda(diferenca)} (sobra)"
    else:
        texto_diferenca = f"- {_moeda(abs(diferenca))} (falta)"

    partes.append(_negrito(True))
    partes.append(_linha_dupla_coluna("Diferenca", texto_diferenca, largura))
    partes.append(_negrito(False))

    partes.append(_tamanho_fonte(1, 2))
    partes.append(
        _linha_dupla_coluna(
            "TOTAL GERAL", _moeda(resumo.get("total_geral", 0)), largura
        )
    )
    partes.append(_tamanho_fonte(1, 1))

    partes.append(_divisoria(largura))
    partes.append(_negrito(True))
    partes.append(_linha(f"Movimentacoes do Dia ({len(movimentos)})"))
    partes.append(_negrito(False))

    if not movimentos:
        partes.append(_linha("Nenhuma movimentacao registrada."))

    for mov in movimentos:

        tipo = mov.get("tipo")
        rotulo_tipo = _ROTULOS_TIPO_MOVIMENTO.get(tipo, tipo or "-")

        partes.append(_linha(f"{_data(mov.get('data'))}  {rotulo_tipo}"))

        descricao = mov.get("descricao")
        if descricao:
            partes.append(_linhas_quebradas(f"  {descricao}", largura))

        partes.append(
            _linha_dupla_coluna("", _moeda(mov.get("valor", 0)), largura)
        )

    if observacoes:
        partes.append(_divisoria(largura))
        partes.append(_negrito(True))
        partes.append(_linha("Observacoes do Fechamento"))
        partes.append(_negrito(False))
        partes.append(_linhas_quebradas(observacoes, largura))

    partes.append(_divisoria(largura))
    partes.append(_alinhar(1))
    partes.append(_linha("Este extrato nao tem valor fiscal."))
    partes.append(_linha("Documento gerado pelo Vertex ERP."))

    partes.append(_cortar_papel())

    return b"".join(partes)


# ==================================================
# TESTE
# ==================================================


def gerar_comandos_teste(largura_papel_mm=80):

    largura = _colunas(largura_papel_mm)

    partes = [_INICIALIZAR, _SELECIONAR_PAGINA_CODIGO]
    partes.append(_alinhar(1))
    partes.append(_negrito(True))
    partes.append(_tamanho_fonte(2, 2))
    partes.append(_linha("VERTEX ERP"))
    partes.append(_tamanho_fonte(1, 1))
    partes.append(_linha("Teste de impressao"))
    partes.append(_negrito(False))
    partes.append(_divisoria(largura))
    partes.append(_linhas_quebradas(
        "Se voce esta lendo isso, a impressora termica esta "
        "configurada corretamente!",
        largura,
    ))
    partes.append(_divisoria(largura))
    partes.append(_linha(f"Papel: {largura_papel_mm}mm ({largura} colunas)"))
    partes.append(_cortar_papel())

    return b"".join(partes)


# ==================================================
# ENVIO -- rede (socket cru) ou USB (spooler do Windows em modo RAW,
# que ignora a renderização gráfica do driver -- só repassa os bytes)
# ==================================================


def _enviar_rede(dados_bytes, ip, porta, timeout=5):
    import socket

    with socket.create_connection((ip, porta), timeout=timeout) as conexao:
        conexao.sendall(dados_bytes)


def _enviar_usb(dados_bytes, nome_impressora_windows):
    import win32print

    identificador = win32print.OpenPrinter(nome_impressora_windows)

    try:
        win32print.StartDocPrinter(
            identificador, 1, ("Cupom Vertex ERP", None, "RAW")
        )
        try:
            win32print.StartPagePrinter(identificador)
            win32print.WritePrinter(identificador, dados_bytes)
            win32print.EndPagePrinter(identificador)
        finally:
            win32print.EndDocPrinter(identificador)
    finally:
        win32print.ClosePrinter(identificador)


def _mensagem_erro_amigavel(erro, tipo):

    texto = str(erro)

    if tipo == "rede":
        if "timed out" in texto.lower():
            return (
                "Não consegui conectar na impressora térmica (tempo "
                "esgotado) -- confira se o IP está certo e se a "
                "impressora está ligada e na mesma rede."
            )
        if "refused" in texto.lower():
            return (
                "A impressora recusou a conexão -- confira o IP e a "
                "porta configurados nas Configurações."
            )
        return f"Não consegui conectar na impressora térmica pela rede: {texto}"

    if "access" in texto.lower() or "acesso" in texto.lower():
        return (
            "Sem permissão pra acessar a impressora -- verifique se "
            "ela está compartilhada/acessível pra este usuário do "
            "Windows."
        )

    return f"Não consegui imprimir na impressora térmica (USB): {texto}"


def enviar(dados_bytes, config_impressora):
    """Retorna (ok, mensagem_de_erro_ou_None)."""

    tipo = (config_impressora or {}).get("tipo")

    try:
        if tipo == "rede":
            ip = config_impressora.get("ip")
            if not ip:
                return False, "Configure o IP da impressora térmica nas Configurações."
            porta = int(config_impressora.get("porta") or 9100)
            _enviar_rede(dados_bytes, ip, porta)
            return True, None

        if tipo == "usb":
            nome = config_impressora.get("nome_impressora_windows")
            if not nome:
                return False, "Escolha a impressora térmica (USB) nas Configurações."
            _enviar_usb(dados_bytes, nome)
            return True, None

        return False, "Configure a impressora térmica nas Configurações antes de imprimir."

    except Exception as erro:
        return False, _mensagem_erro_amigavel(erro, tipo)


def listar_impressoras_windows():
    """Nomes das impressoras instaladas no Windows -- usado pra
    preencher o seletor da configuração em modo USB."""

    try:
        import win32print

        impressoras = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
        return sorted({item[2] for item in impressoras})
    except Exception:
        return []


# ==================================================
# API DE ALTO NÍVEL
# ==================================================


def imprimir_comprovante(dados, config_loja, logo_bytes, config_impressora):
    largura_papel_mm = (config_impressora or {}).get("largura_papel") or 80
    comandos = gerar_comandos_comprovante(dados, config_loja, logo_bytes, largura_papel_mm)
    return enviar(comandos, config_impressora)


def imprimir_recibo_pagamento(
    cliente_nome, valor, forma_pagamento, saldo_antes, saldo_depois,
    responsavel, momento, config_loja, config_impressora,
):
    largura_papel_mm = (config_impressora or {}).get("largura_papel") or 80
    comandos = gerar_comandos_recibo_pagamento(
        cliente_nome, valor, forma_pagamento, saldo_antes, saldo_depois,
        responsavel, momento, config_loja, largura_papel_mm,
    )
    return enviar(comandos, config_impressora)


def imprimir_extrato(
    cliente, movimentos, observacoes, saldo, responsavel, config_loja, config_impressora,
):
    largura_papel_mm = (config_impressora or {}).get("largura_papel") or 80
    comandos = gerar_comandos_extrato(
        cliente, movimentos, observacoes, saldo, responsavel, config_loja, largura_papel_mm,
    )
    return enviar(comandos, config_impressora)


def imprimir_fechamento_caixa(
    caixa, resumo, movimentos, valor_contado, observacoes, responsavel,
    fechado_em, config_loja, config_impressora,
):
    largura_papel_mm = (config_impressora or {}).get("largura_papel") or 80
    comandos = gerar_comandos_fechamento_caixa(
        caixa, resumo, movimentos, valor_contado, observacoes, responsavel,
        fechado_em, config_loja, largura_papel_mm,
    )
    return enviar(comandos, config_impressora)


def imprimir_teste(config_impressora):
    largura_papel_mm = (config_impressora or {}).get("largura_papel") or 80
    comandos = gerar_comandos_teste(largura_papel_mm)
    return enviar(comandos, config_impressora)
