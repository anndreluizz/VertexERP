import io

from PIL import Image

from app.utils.imagem import LADO_MAXIMO, reduzir_imagem


def _png(largura, altura, modo="RGB"):
    img = Image.effect_noise((largura, altura), 60).convert(modo)  # ruido: nao comprime de graca
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_foto_grande_fica_menor_e_cabe_na_tela():
    original = _png(3000, 2000)
    reduzida = reduzir_imagem(original)
    img = Image.open(io.BytesIO(reduzida))
    assert img.format == "JPEG"
    assert img.size == (LADO_MAXIMO, 683)  # mantem a proporcao 3:2
    assert len(reduzida) < len(original) / 5


def test_png_transparente_vira_jpeg():
    img = Image.open(io.BytesIO(reduzir_imagem(_png(1500, 1500, "RGBA"))))
    assert img.mode == "RGB"


def test_nao_imagem_volta_igual():
    assert reduzir_imagem(b"nao sou foto") == b"nao sou foto"


def test_foto_pequena_nao_piora():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "red").save(buf, "JPEG", quality=30)
    assert reduzir_imagem(buf.getvalue()) == buf.getvalue()
