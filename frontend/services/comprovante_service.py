import base64
import os
import tempfile
from datetime import datetime
from io import BytesIO

import qrcode
from PySide6.QtGui import QTextDocument, QPageSize, QImage
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import QFileDialog, QMessageBox

from services.api import get, post, configuracoes
from utils.formatacao import formatar_moeda


# ==================================================
# DADOS
# ==================================================


def buscar_dados_comprovante(venda_id):
    """Tudo que o comprovante precisa (venda + cliente + saldo devedor
    + itens com nome do produto), numa unica chamada -- ver
    VendaService.montar_comprovante no backend."""

    response = get(f"/vendas/{venda_id}/comprovante")

    if response.status_code != 200:
        return None

    return response.json()


def buscar_historico_envios(venda_id):

    response = get(f"/vendas/{venda_id}/comprovante-envios")

    if response.status_code != 200:
        return []

    return response.json()


def obter_logo_loja():
    """Bytes do logo da loja, ou None se não tiver logo cadastrado --
    mesmo padrão de obter_foto_cliente."""

    response = get("/configuracoes/logo")

    if response.status_code != 200:
        return None

    return response.content


# ==================================================
# ENVIO
# ==================================================


def enviar_whatsapp(venda_id, pdf_bytes, legenda, nome_arquivo="comprovante.pdf"):

    pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")

    return post(
        f"/vendas/{venda_id}/comprovante/whatsapp",
        {
            "pdf_base64": pdf_base64,
            "nome_arquivo": nome_arquivo,
            "legenda": legenda,
        },
    )


def enviar_email(
    venda_id,
    pdf_bytes,
    destinatario=None,
    assunto="Comprovante da sua compra",
    corpo="",
    nome_arquivo="comprovante.pdf",
):

    pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")

    return post(
        f"/vendas/{venda_id}/comprovante/email",
        {
            "pdf_base64": pdf_base64,
            "destinatario": destinatario,
            "assunto": assunto,
            "corpo": corpo,
            "nome_arquivo": nome_arquivo,
        },
    )


def mensagem_whatsapp_padrao(cliente_nome, nome_loja):

    primeiro_nome = (cliente_nome or "").strip().split(" ")[0] or "cliente"

    return (
        f"Olá, {primeiro_nome}!\n\n"
        f"Agradecemos pela sua compra na {nome_loja}.\n\n"
        f"Segue em anexo o comprovante da sua compra.\n\n"
        f"Qualquer dúvida estamos à disposição.\n\n"
        f"Atenciosamente,\n"
        f"Equipe {nome_loja}."
    )


# ==================================================
# QR CODE
# ==================================================


def _gerar_qrcode_base64(texto):
    """box_size baixo pra gerar um PNG de origem já pequeno -- o
    QTextDocument (usado pra imprimir/exportar o comprovante) ignora
    width/height definidos via CSS em <img>, só respeita os atributos
    HTML width/height (ver gerar_html_comprovante). Sem isso, o PNG
    nativo do qrcode (bem maior, ~500-800px) força a largura do
    documento inteiro e encolhe todo o resto do texto pra caber."""

    qr = qrcode.QRCode(box_size=3, border=2)
    qr.add_data(texto)
    qr.make(fit=True)
    imagem = qr.make_image()

    buffer = BytesIO()
    imagem.save(buffer, format="PNG")

    return base64.b64encode(buffer.getvalue()).decode("ascii")


# ==================================================
# HTML
# ==================================================


def _formatar_moeda(valor):
    return formatar_moeda(valor, com_simbolo=True)


def _formatar_data(data_iso):

    if not data_iso:
        return "—"

    texto = str(data_iso).replace("T", " ")

    try:
        dt = datetime.fromisoformat(texto[:19])
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return texto[:16]


def gerar_html_comprovante(dados, config, logo_bytes=None):
    """Monta o HTML completo do comprovante -- logo, dados da loja,
    numero da venda, cliente, vendedor, itens, desconto/acrescimo,
    forma de pagamento, situacao (pago/fiado), saldo devedor
    atualizado, observacoes e QR Code. Renderizado depois via
    QTextDocument (ver montar_documento) tanto pra tela quanto pra
    impressão/PDF.

    Font-size sempre em pt, nunca em px: o QTextDocument usa DPI da
    TELA (~96) quando exibido num QTextBrowser, mas o QPrinter usa o
    DPI real da impressora/PDF (bem mais alto) -- um font-size em px
    fica proporcional ao DPI e sai minúsculo no papel/PDF mesmo
    aparecendo normal na tela. Em pt (unidade física, 1/72") o texto
    sai do mesmo tamanho nos dois casos. Larguras/margens em px estão
    OK (não sofrem esse problema); só tamanho de fonte precisa ser pt.
    Pelo mesmo motivo, as tags <img> aqui usam os atributos width/
    height do HTML (não CSS): o QTextDocument não aplica width/height
    de imagem via style=, só via atributo -- sem isso o QR Code (ou
    logo) nasce no tamanho nativo do PNG e "empurra" a largura do
    documento inteiro, encolhendo visualmente todo o resto do texto
    junto (ver _gerar_qrcode_base64 e o cálculo de largura do logo
    abaixo)."""

    nome_loja = config.get("nome_loja") or "Vertex ERP"
    endereco_loja = config.get("endereco") or ""
    telefone_loja = config.get("telefone") or ""
    cnpj_loja = config.get("cnpj_cpf") or ""

    logo_html = ""
    if logo_bytes:

        # QTextDocument ignora max-height/max-width em CSS -- so
        # respeita width/height como atributo HTML de verdade, entao
        # precisa calcular o tamanho final (mantendo proporcao) aqui
        # em vez de deixar por conta do CSS.
        imagem_logo = QImage.fromData(logo_bytes)
        largura_original = imagem_logo.width() or 1
        altura_original = imagem_logo.height() or 1

        altura_alvo = 70
        largura_alvo = round(largura_original * (altura_alvo / altura_original))

        if largura_alvo > 200:
            largura_alvo = 200
            altura_alvo = round(altura_original * (largura_alvo / largura_original))

        logo_b64 = base64.b64encode(logo_bytes).decode("ascii")
        logo_html = (
            f'<img src="data:image/png;base64,{logo_b64}" '
            f'width="{largura_alvo}" height="{altura_alvo}" '
            f'style="margin-bottom:6px;" />'
        )

    linhas_itens = "".join(
        "<tr>"
        f"<td style='padding:6px 8px; border-bottom:1px solid #E5E7EB;'>"
        f"{item['nome']}</td>"
        f"<td style='padding:6px 8px; border-bottom:1px solid #E5E7EB; "
        f"text-align:center;'>{item['quantidade']}</td>"
        f"<td style='padding:6px 8px; border-bottom:1px solid #E5E7EB; "
        f"text-align:right;'>{_formatar_moeda(item['valor_unitario'])}</td>"
        f"<td style='padding:6px 8px; border-bottom:1px solid #E5E7EB; "
        f"text-align:right;'>{_formatar_moeda(item['subtotal'])}</td>"
        "</tr>"
        for item in dados["itens"]
    )

    desconto = float(dados.get("desconto") or 0)

    if desconto > 0:
        linha_ajuste = (
            f"<p style='margin:4px 0;'>Desconto: "
            f"-{_formatar_moeda(desconto)}</p>"
        )
    elif desconto < 0:
        linha_ajuste = (
            f"<p style='margin:4px 0;'>Acréscimo: "
            f"+{_formatar_moeda(-desconto)}</p>"
        )
    else:
        linha_ajuste = ""

    if dados.get("forma_pagamento_2"):
        valor_principal = float(dados["valor_total"]) - float(
            dados.get("valor_forma_2") or 0
        )
        linha_pagamento = (
            f"<p style='margin:4px 0;'>Forma de pagamento: "
            f"{_formatar_moeda(valor_principal)} ({dados['forma_pagamento']}) + "
            f"{_formatar_moeda(dados['valor_forma_2'])} ({dados['forma_pagamento_2']})</p>"
        )
    else:
        linha_pagamento = (
            f"<p style='margin:4px 0;'>Forma de pagamento: "
            f"{dados['forma_pagamento']}</p>"
        )

    situacao = dados.get("situacao") or "PAGO"
    cor_situacao = "#DC2626" if situacao == "FIADO" else "#16A34A"
    texto_situacao = "Fiado (a prazo)" if situacao == "FIADO" else "Pago"

    linha_saldo = ""
    saldo = dados.get("saldo_devedor_cliente")
    if situacao == "FIADO" and saldo is not None:
        linha_saldo = (
            f"<p style='margin:4px 0; color:{cor_situacao}; font-weight:bold;'>"
            f"Saldo devedor atualizado: {_formatar_moeda(saldo)}</p>"
        )

    cliente_nome = dados.get("cliente_nome")
    cliente_linhas = ""
    if cliente_nome:
        cliente_linhas += f"<p style='margin:4px 0;'>Cliente: {cliente_nome}</p>"
        if dados.get("cliente_cpf_cnpj"):
            cliente_linhas += (
                f"<p style='margin:4px 0;'>CPF/CNPJ: "
                f"{dados['cliente_cpf_cnpj']}</p>"
            )

    vendedor_linha = (
        f"<p style='margin:4px 0;'>Vendedor: {dados['usuario_nome']}</p>"
        if dados.get("usuario_nome") else ""
    )

    observacao_linha = (
        f"<p style='margin:4px 0;'>Observações: {dados['observacao']}</p>"
        if dados.get("observacao") else ""
    )

    texto_qr = (
        f"Vertex ERP | {nome_loja} | Venda #{dados['venda_id']} | "
        f"{_formatar_data(dados['data'])} | "
        f"Total: {_formatar_moeda(dados['valor_total'])}"
    )
    qr_b64 = _gerar_qrcode_base64(texto_qr)

    return f"""
    <html>
    <body style="font-family: Arial; font-size: 10pt; color:#1E293B;">
        <div style="text-align:center;">
            {logo_html}
            <h2 style="margin:2px 0;">{nome_loja}</h2>
            {f"<p style='margin:0; color:#64748B;'>{endereco_loja}</p>" if endereco_loja else ""}
            {f"<p style='margin:0; color:#64748B;'>{telefone_loja}</p>" if telefone_loja else ""}
            {f"<p style='margin:0; color:#64748B;'>CNPJ: {cnpj_loja}</p>" if cnpj_loja else ""}
        </div>
        <hr style="border:none; border-top:1px solid #E5E7EB; margin:10px 0;">
        <p style="margin:4px 0;"><b>Venda #{dados['venda_id']}</b></p>
        <p style="margin:4px 0;">Data: {_formatar_data(dados['data'])}</p>
        {vendedor_linha}
        {cliente_linhas}
        <table style="width:100%; border-collapse:collapse; margin-top:10px;">
            <tr style="background:#F1F5F9;">
                <th style="padding:6px 8px; text-align:left;">Produto</th>
                <th style="padding:6px 8px;">Qtd</th>
                <th style="padding:6px 8px; text-align:right;">Unitário</th>
                <th style="padding:6px 8px; text-align:right;">Subtotal</th>
            </tr>
            {linhas_itens}
        </table>
        {linha_ajuste}
        <h3 style="text-align:right; margin-top:12px;">
            Total: {_formatar_moeda(dados['valor_total'])}
        </h3>
        {linha_pagamento}
        <p style="margin:4px 0;">
            Situação:
            <span style="color:{cor_situacao}; font-weight:bold;">
                {texto_situacao}
            </span>
        </p>
        {linha_saldo}
        {observacao_linha}
        <div style="text-align:center; margin-top:16px;">
            <img src="data:image/png;base64,{qr_b64}"
                 width="110" height="110" />
        </div>
        <hr style="border:none; border-top:1px solid #E5E7EB; margin:10px 0;">
        <p style="color:#94A3B8; font-size:8pt; text-align:center;">
            Este comprovante não tem valor fiscal.<br>
            Documento gerado automaticamente pelo Vertex ERP.
        </p>
    </body>
    </html>
    """


# ==================================================
# RENDERIZAÇÃO / PDF / IMPRESSÃO
# ==================================================


def montar_documento(html):
    documento = QTextDocument()
    documento.setHtml(html)
    return documento


def gerar_pdf_bytes(html):
    """Gera os bytes do PDF sem pedir caminho pro usuário -- usado
    pra anexar automaticamente no envio por WhatsApp/e-mail. QPrinter
    só sabe escrever em um arquivo de verdade, então usa um temporário
    e apaga na sequência."""

    caminho_temp = os.path.join(
        tempfile.gettempdir(),
        f"vertexerp_comprovante_{os.getpid()}_{id(html)}.pdf",
    )

    try:
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(caminho_temp)
        printer.setPageSize(QPageSize(QPageSize.A5))

        montar_documento(html).print_(printer)

        with open(caminho_temp, "rb") as arquivo:
            return arquivo.read()

    finally:
        if os.path.exists(caminho_temp):
            os.remove(caminho_temp)


def salvar_pdf(html, parent, nome_sugerido="comprovante.pdf"):

    caminho, _ = QFileDialog.getSaveFileName(
        parent,
        "Salvar Comprovante",
        nome_sugerido,
        "Arquivo PDF (*.pdf)",
    )

    if not caminho:
        return False

    if not caminho.lower().endswith(".pdf"):
        caminho += ".pdf"

    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(caminho)
    printer.setPageSize(QPageSize(QPageSize.A5))

    montar_documento(html).print_(printer)

    QMessageBox.information(
        parent,
        "Sucesso",
        "Comprovante salvo em PDF com sucesso.",
    )

    return True


def imprimir(html, parent):

    printer = QPrinter(QPrinter.HighResolution)

    dialogo = QPrintDialog(printer, parent)

    if dialogo.exec() != QPrintDialog.Accepted:
        return False

    montar_documento(html).print_(printer)

    return True
