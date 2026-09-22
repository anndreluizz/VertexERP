"""HTML compartilhado entre todo documento impresso/PDF do sistema
(comprovante de venda, extrato de cliente, recibo de despesa,
orçamento do PDV, relatório) -- antes cada tela tinha sua própria
cópia quase idêntica desse cabeçalho/tabela/total, com pequenas
divergências visuais entre elas (ver Fase 6, Onda 5).

Cores fixas de propósito, independente do tema do app -- documento
impresso é a exceção documentada em CLAUDE.md a "nunca cor hex direto
numa tela": aqui não existe "tema escuro" de papel/PDF.

Renderizado via QTextDocument (ver services/comprovante_service.py:
montar_documento/gerar_pdf_bytes/salvar_pdf/imprimir, reaproveitados
por todo mundo que usa este módulo) -- por isso font-size sempre em
pt (nunca px, que sai minúsculo no PDF por causa do DPI da
impressora) e imagem sempre com width/height como atributo HTML (não
CSS, que o QTextDocument ignora em <img>)."""

import base64

from PySide6.QtGui import QImage

COR_PRIMARIA = "#2563EB"
COR_TEXTO = "#1E293B"
COR_TEXTO_SECUNDARIO = "#64748B"
COR_TEXTO_TERCIARIO = "#94A3B8"
COR_BORDA = "#E5E7EB"
COR_FUNDO_CLARO = "#EFF6FF"
COR_TEXTO_DESTAQUE = "#1E3A8A"

ESTILO_BODY = f"font-family: Arial; font-size: 10pt; color:{COR_TEXTO};"


def _logo_html(logo_bytes):

    if not logo_bytes:
        return ""

    imagem = QImage.fromData(logo_bytes)
    largura_original = imagem.width() or 1
    altura_original = imagem.height() or 1

    altura_alvo = 70
    largura_alvo = round(largura_original * (altura_alvo / altura_original))

    if largura_alvo > 200:
        largura_alvo = 200
        altura_alvo = round(altura_original * (largura_alvo / largura_original))

    logo_b64 = base64.b64encode(logo_bytes).decode("ascii")

    return (
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'width="{largura_alvo}" height="{altura_alvo}" '
        f'style="margin-bottom:6px;" />'
    )


def cabecalho_html(titulo_documento, config, logo_bytes=None):
    """Barra fina colorida + logo (se tiver) + nome/endereço/telefone/
    CNPJ da loja + faixa colorida com o título do documento (ex.:
    "COMPROVANTE DE VENDA", "EXTRATO FINANCEIRO")."""

    nome_loja = config.get("nome_loja") or "Vertex ERP"
    endereco_loja = config.get("endereco") or ""
    telefone_loja = config.get("telefone") or ""
    cnpj_loja = config.get("cnpj_cpf") or ""

    return f"""
    <table width="100%" style="margin-bottom:14px;">
        <tr><td style="background:{COR_PRIMARIA}; height:4px; font-size:1px;">&nbsp;</td></tr>
    </table>
    <div style="text-align:center;">
        {_logo_html(logo_bytes)}
        <h2 style="margin:2px 0;">{nome_loja}</h2>
        {f"<p style='margin:0; color:{COR_TEXTO_SECUNDARIO};'>{endereco_loja}</p>" if endereco_loja else ""}
        {f"<p style='margin:0; color:{COR_TEXTO_SECUNDARIO};'>WhatsApp: {telefone_loja}</p>" if telefone_loja else ""}
        {f"<p style='margin:0; color:{COR_TEXTO_SECUNDARIO};'>CNPJ: {cnpj_loja}</p>" if cnpj_loja else ""}
    </div>
    <table width="100%" style="margin:14px 0;">
        <tr><td style="background:{COR_PRIMARIA}; padding:8px; text-align:center;">
            <span style="color:#FFFFFF; font-size:12pt; font-weight:bold;">
                {titulo_documento}
            </span>
        </td></tr>
    </table>
    """


def cabecalho_tabela(colunas, alinhamentos=None):
    """<tr> de cabeçalho de tabela (fundo azul claro, texto azul
    escuro) -- `alinhamentos` é uma lista paralela a `colunas`
    ("left"/"center"/"right"), default "left"."""

    alinhamentos = alinhamentos or ["left"] * len(colunas)

    celulas = "".join(
        f"<th style='padding:7px 8px; text-align:{alinhamento}; "
        f"color:{COR_TEXTO_DESTAQUE};'>{coluna}</th>"
        for coluna, alinhamento in zip(colunas, alinhamentos)
    )

    return f"<tr style='background:{COR_FUNDO_CLARO};'>{celulas}</tr>"


def linha_zebra(celulas, indice, alinhamentos=None):
    """<tr> de uma linha de dados com zebra striping por par/ímpar --
    feito em Python porque o QTextDocument não entende seletor
    :nth-child em CSS. `alinhamentos` é uma lista paralela a
    `celulas` ("left"/"center"/"right"), default "left"."""

    alinhamentos = alinhamentos or ["left"] * len(celulas)
    cor_fundo = "#FFFFFF" if indice % 2 == 0 else "#F8FAFC"

    tds = "".join(
        f"<td style='padding:7px 8px; border-bottom:1px solid {COR_BORDA}; "
        f"text-align:{alinhamento};'>{valor}</td>"
        for valor, alinhamento in zip(celulas, alinhamentos)
    )

    return f"<tr style='background:{cor_fundo};'>{tds}</tr>"


def bloco_total(rotulo, valor_formatado):
    """Caixa de destaque de total (fundo azul claro, valor grande em
    negrito) -- mesmo estilo em todo documento que fecha com um
    total (comprovante de venda, extrato, relatório)."""

    return f"""
    <table width="100%" style="margin-top:14px;">
        <tr><td style="background:{COR_FUNDO_CLARO}; padding:10px 14px; text-align:right;">
            <span style="font-size:8pt; color:{COR_PRIMARIA}; font-weight:bold;">
                {rotulo}
            </span><br>
            <span style="font-size:15pt; color:{COR_TEXTO}; font-weight:bold;">
                {valor_formatado}
            </span>
        </td></tr>
    </table>
    """


def rodape_nao_fiscal(texto="Este documento não possui valor fiscal."):

    return f"""
    <hr style="border:none; border-top:1px solid {COR_BORDA}; margin:14px 0 8px;">
    <p style="color:{COR_TEXTO_TERCIARIO}; font-size:8pt; text-align:center;">
        {texto}
    </p>
    """
