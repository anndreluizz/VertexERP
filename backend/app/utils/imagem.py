"""Fotos (produto/cliente) chegam do celular no tamanho da camera (~1 MB
cada) e ficam no banco -- e em cada backup .sql, em hex, o dobro disso.
Em 19/10 55 fotos levaram o backup de 9 MB pra 247 MB. Reduz tudo pra
caber numa tela (LADO_MAXIMO) antes de gravar."""

import base64
import io

from PIL import Image, ImageOps

LADO_MAXIMO = 1024
QUALIDADE_JPEG = 82


def reduzir_imagem(dados: bytes) -> bytes:
    """JPEG de no maximo LADO_MAXIMO px. Se nao for imagem que o Pillow
    abra, ou se a reducao nao ficar menor, devolve o original."""
    try:
        aberta = Image.open(io.BytesIO(dados))
        if aberta.format == "JPEG" and max(aberta.size) <= LADO_MAXIMO:
            return dados  # ja serve: recomprimir so' perderia qualidade
        img = ImageOps.exif_transpose(aberta)
        img.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
        if img.mode != "RGB":  # PNG transparente/paleta -> fundo branco
            rgba = img.convert("RGBA")
            img = Image.new("RGB", rgba.size, "white")
            img.paste(rgba, mask=rgba.getchannel("A"))
        saida = io.BytesIO()
        img.save(saida, "JPEG", quality=QUALIDADE_JPEG, optimize=True)
    except Exception:
        return dados
    return saida.getvalue() if saida.tell() < len(dados) else dados


def decodificar_foto(foto_base64: str) -> bytes:
    return reduzir_imagem(base64.b64decode(foto_base64))
