"""Parser de NF-e (Nota Fiscal Eletronica) -- so' biblioteca padrao, sem
IA nem dependencia nova: o formato e' estruturado e conhecido (XML padrao
SEFAZ), diferente de um PDF de layout livre por fornecedor."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


class NFeInvalidaError(ValueError):
    """Arquivo enviado nao e' uma NF-e reconhecivel, ou e' uma NF-e
    cancelada/denegada -- mensagem ja pronta pra virar 400 pelo handler
    global (ver main.py)."""


@dataclass
class ItemNFeExtraido:
    codigo: str
    descricao: str
    codigo_barras: str | None
    quantidade: Decimal
    valor_unitario: Decimal


@dataclass
class FornecedorNFeExtraido:
    cnpj: str
    razao_social: str
    nome_fantasia: str | None


@dataclass
class NFeExtraida:
    fornecedor: FornecedorNFeExtraido
    itens: list[ItemNFeExtraido] = field(default_factory=list)


def _somente_digitos(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


def _texto(elemento, tag: str) -> str | None:
    filho = elemento.find(f"nfe:{tag}", NS)
    if filho is None or not (filho.text or "").strip():
        return None
    return filho.text.strip()


def _quantidade(texto: str | None) -> Decimal:
    """qCom vem como decimal (ex.: "10.0000", "2.3500" kg) -- guarda
    com 3 casas, igual Produto.estoque."""

    if not texto:
        raise NFeInvalidaError("Item da NF-e sem quantidade (qCom).")

    try:
        decimal = Decimal(texto)
    except InvalidOperation:
        raise NFeInvalidaError(f"Quantidade inválida na NF-e: '{texto}'.")

    return decimal.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _valor_decimal(texto: str | None, campo: str) -> Decimal:
    if not texto:
        raise NFeInvalidaError(f"Item da NF-e sem {campo}.")

    try:
        return Decimal(texto)
    except InvalidOperation:
        raise NFeInvalidaError(f"Valor inválido em {campo}: '{texto}'.")


def _extrair_item(det) -> ItemNFeExtraido:
    prod = det.find("nfe:prod", NS)

    if prod is None:
        raise NFeInvalidaError("Item da NF-e sem dados de produto (prod).")

    codigo = _texto(prod, "cProd")
    descricao = _texto(prod, "xProd")

    if not codigo or not descricao:
        raise NFeInvalidaError(
            "Item da NF-e sem código (cProd) ou descrição (xProd)."
        )

    codigo_barras = _texto(prod, "cEAN")
    if codigo_barras == "SEM GTIN":
        codigo_barras = None

    return ItemNFeExtraido(
        codigo=codigo,
        descricao=descricao,
        codigo_barras=codigo_barras,
        quantidade=_quantidade(_texto(prod, "qCom")),
        valor_unitario=_valor_decimal(_texto(prod, "vUnCom"), "vUnCom"),
    )


def parsear_nfe(xml_conteudo: str) -> NFeExtraida:
    try:
        root = ET.fromstring(xml_conteudo)
    except ET.ParseError as exc:
        raise NFeInvalidaError(f"Arquivo XML inválido: {exc}") from exc

    # ".//" cobre tanto <nfeProc><NFe><infNFe> quanto <NFe><infNFe> direto
    # (sem o wrapper de protocolo), sem precisar checar a raiz na mao.
    inf_nfe = root.find(".//nfe:infNFe", NS)

    if inf_nfe is None:
        raise NFeInvalidaError(
            "Arquivo não é uma NF-e reconhecível (tag infNFe não encontrada)."
        )

    emit = inf_nfe.find("nfe:emit", NS)
    dets = inf_nfe.findall("nfe:det", NS)

    if emit is None:
        raise NFeInvalidaError("NF-e sem dados do emitente (tag emit ausente).")

    if not dets:
        raise NFeInvalidaError("NF-e sem nenhum item (tag det ausente).")

    cnpj = _texto(emit, "CNPJ")

    if not cnpj:
        raise NFeInvalidaError(
            "Emitente sem CNPJ (só CPF) — fora de escopo, a importação "
            "exige fornecedor pessoa jurídica."
        )

    # cStat so' existe quando o XML tem o wrapper nfeProc/protNFe (nota ja
    # processada pela SEFAZ) -- se so' vier o <NFe> cru, nao ha como
    # checar autorizacao e a importacao segue sem essa validacao extra.
    cstat = root.find(".//nfe:protNFe/nfe:infProt/nfe:cStat", NS)

    if cstat is not None and (cstat.text or "").strip() != "100":
        raise NFeInvalidaError(
            f"NF-e não está autorizada (cStat={cstat.text}) — não pode "
            "ser importada."
        )

    fornecedor = FornecedorNFeExtraido(
        cnpj=_somente_digitos(cnpj),
        razao_social=_texto(emit, "xNome") or "",
        nome_fantasia=_texto(emit, "xFant"),
    )

    if not fornecedor.razao_social:
        raise NFeInvalidaError("Emitente sem razão social (xNome).")

    return NFeExtraida(
        fornecedor=fornecedor,
        itens=[_extrair_item(det) for det in dets],
    )


if __name__ == "__main__":
    _XML_VALIDO = """<?xml version="1.0" encoding="UTF-8"?>
    <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
      <NFe>
        <infNFe Id="NFe1" versao="4.00">
          <emit>
            <CNPJ>12345678000199</CNPJ>
            <xNome>Fornecedor Teste Ltda</xNome>
            <xFant>Fornecedor Teste</xFant>
          </emit>
          <det nItem="1">
            <prod>
              <cProd>ABC123</cProd>
              <cEAN>7891234567890</cEAN>
              <xProd>Produto Um</xProd>
              <qCom>10.0000</qCom>
              <vUnCom>15.5000</vUnCom>
            </prod>
          </det>
          <det nItem="2">
            <prod>
              <cProd>DEF456</cProd>
              <cEAN>SEM GTIN</cEAN>
              <xProd>Produto Dois</xProd>
              <qCom>3.0000</qCom>
              <vUnCom>7.2500</vUnCom>
            </prod>
          </det>
        </infNFe>
      </NFe>
      <protNFe>
        <infProt>
          <cStat>100</cStat>
        </infProt>
      </protNFe>
    </nfeProc>"""

    extraida = parsear_nfe(_XML_VALIDO)
    assert extraida.fornecedor.cnpj == "12345678000199"
    assert extraida.fornecedor.razao_social == "Fornecedor Teste Ltda"
    assert len(extraida.itens) == 2
    assert extraida.itens[0].quantidade == 10
    assert extraida.itens[0].valor_unitario == Decimal("15.5000")
    assert extraida.itens[1].codigo_barras is None

    _XML_INVALIDO = "<algumaOutraCoisa></algumaOutraCoisa>"
    try:
        parsear_nfe(_XML_INVALIDO)
        raise SystemExit("deveria ter levantado NFeInvalidaError")
    except NFeInvalidaError:
        pass

    print("nfe_service: smoke test ok")
