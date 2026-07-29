import unicodedata


def _remover_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def _campo(id_campo: str, valor: str) -> str:
    tamanho = f"{len(valor):02d}"
    return f"{id_campo}{tamanho}{valor}"


def _crc16_ccitt(dados: str) -> str:

    crc = 0xFFFF

    for byte in dados.encode("utf-8"):

        crc ^= byte << 8

        for _ in range(8):

            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1

            crc &= 0xFFFF

    return format(crc, "04X")


def montar_payload_pix(
    chave: str,
    nome: str,
    cidade: str,
    valor: float,
    txid: str = "***",
) -> str:
    """Monta o payload (BR Code / EMV) de um QR Code PIX estático
    com valor fixo, no formato lido pelos apps dos bancos."""

    nome = _remover_acentos(nome).upper()[:25].strip() or "LOJA"
    cidade = _remover_acentos(cidade).upper()[:15].strip() or "BRASIL"

    merchant_account = (
        _campo("00", "br.gov.bcb.pix")
        + _campo("01", chave)
    )

    payload = (
        _campo("00", "01")
        + _campo("01", "12")
        + _campo("26", merchant_account)
        + _campo("52", "0000")
        + _campo("53", "986")
        + _campo("54", f"{valor:.2f}")
        + _campo("58", "BR")
        + _campo("59", nome)
        + _campo("60", cidade)
        + _campo("62", _campo("05", txid))
    )

    payload_com_crc_id = payload + "6304"

    crc = _crc16_ccitt(payload_com_crc_id)

    return payload_com_crc_id + crc
