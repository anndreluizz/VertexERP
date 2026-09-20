import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation


@dataclass
class TransacaoOfx:
    fitid: str
    data: date
    descricao: str
    valor: Decimal
    tipo: str  # CREDITO ou DEBITO


@dataclass
class ExtratoOfx:
    banco: str | None
    conta: str | None
    transacoes: list[TransacaoOfx]


def _campo(bloco: str, tag: str) -> str | None:
    """OFX v1 (SGML) normalmente nao fecha tag de folha (<TAG>valor sem
    </TAG>), so' as de container (<STMTTRN>...</STMTTRN>) -- por isso
    um parser XML de verdade (xml.etree, ja usado pro XML da NF-e, que
    e' XML valido) quebra aqui. Regex pegando ate a proxima tag ou
    quebra de linha resolve os dois formatos (v1 SGML e v2 XML) sem
    precisar de biblioteca nova."""

    match = re.search(
        rf"<{tag}>\s*([^\r\n<]+)", bloco, re.IGNORECASE
    )
    return match.group(1).strip() if match else None


def _parse_data(valor: str) -> date | None:
    # "20260901120000[-3:BRT]" ou so' "20260901" -- os 8 primeiros
    # digitos sao sempre AAAAMMDD no OFX
    digitos = re.match(r"(\d{8})", valor or "")
    if not digitos:
        return None

    texto = digitos.group(1)
    try:
        return date(int(texto[0:4]), int(texto[4:6]), int(texto[6:8]))
    except ValueError:
        return None


def parse_ofx(conteudo: str) -> ExtratoOfx:

    banco = _campo(conteudo, "BANKID") or _campo(conteudo, "ORG")
    conta = _campo(conteudo, "ACCTID")

    transacoes = []

    for bloco in re.findall(
        r"<STMTTRN>(.*?)</STMTTRN>", conteudo, re.IGNORECASE | re.DOTALL
    ):
        fitid = _campo(bloco, "FITID")
        valor_texto = _campo(bloco, "TRNAMT")
        data_texto = _campo(bloco, "DTPOSTED")

        if not fitid or not valor_texto or not data_texto:
            continue

        data_transacao = _parse_data(data_texto)
        if data_transacao is None:
            continue

        try:
            valor = Decimal(valor_texto.replace(",", "."))
        except InvalidOperation:
            continue

        descricao = (
            _campo(bloco, "MEMO") or _campo(bloco, "NAME") or ""
        )

        transacoes.append(
            TransacaoOfx(
                fitid=fitid,
                data=data_transacao,
                descricao=descricao,
                valor=valor,
                tipo="CREDITO" if valor >= 0 else "DEBITO",
            )
        )

    return ExtratoOfx(banco=banco, conta=conta, transacoes=transacoes)
