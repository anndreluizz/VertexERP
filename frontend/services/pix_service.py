import io
import unicodedata

import qrcode
from PySide6.QtGui import QPixmap


def _normalizar(texto: str, tamanho_max: int) -> str:
    """Remove acentos e caracteres especiais — o padrão BR Code exige
    texto em ASCII simples nesses campos."""

    texto = (
        unicodedata.normalize("NFKD", texto)
        .encode("ascii", "ignore")
        .decode("ascii")
    )

    return texto.upper().strip()[:tamanho_max]


def _campo(id_: str, valor: str) -> str:
    return f"{id_}{len(valor):02d}{valor}"


def _crc16_ccitt(payload: str) -> str:
    """CRC16-CCITT (poly 0x1021, init 0xFFFF) — checksum exigido no
    final de todo BR Code (Pix Copia e Cola)."""

    crc = 0xFFFF

    for byte in payload.encode("utf-8"):
        crc ^= byte << 8

        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF

    return f"{crc:04X}"


def gerar_payload_pix(valor: float, chave: str, nome: str, cidade: str) -> str:
    """Monta o BR Code estático (com valor) do Pix Copia e Cola."""

    nome = _normalizar(nome, 25)
    cidade = _normalizar(cidade, 15)

    conta = _campo("00", "BR.GOV.BCB.PIX") + _campo("01", chave)

    payload_sem_crc = (
        _campo("00", "01")
        + _campo("01", "11")
        + _campo("26", conta)
        + _campo("52", "0000")
        + _campo("53", "986")
        + _campo("54", f"{valor:.2f}")
        + _campo("58", "BR")
        + _campo("59", nome)
        + _campo("60", cidade)
        + _campo("62", _campo("05", "***"))
        + "6304"
    )

    return payload_sem_crc + _crc16_ccitt(payload_sem_crc)


def gerar_qrcode_pixmap(payload: str) -> QPixmap:

    imagem = qrcode.make(payload)

    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")

    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue())

    return pixmap
