"""Leitura de boleto: linha digitável (47/48 dígitos), código de barras
(44) e PDF. Só biblioteca padrão + pypdf -- o formato é o da FEBRABAN,
estruturado e conhecido.

O que o código traz: banco, valor e vencimento (boleto bancário) ou
valor e tipo de empresa (conta de consumo: luz, água, telefone). O NOME
do beneficiário não vem no código -- vem do PDF, ou o sistema aprende
(ver BeneficiarioBoleto e chave_beneficiario)."""

import re
from datetime import date, timedelta
from decimal import Decimal

BANCOS = {
    "001": "Banco do Brasil", "004": "Banco do Nordeste", "033": "Santander",
    "037": "Banpará", "041": "Banrisul", "070": "BRB", "077": "Inter",
    "084": "Uniprime", "085": "Ailos", "104": "Caixa", "136": "Unicred",
    "197": "Stone", "208": "BTG Pactual", "212": "Banco Original",
    "218": "BS2", "237": "Bradesco", "260": "Nubank", "290": "PagBank",
    "323": "Mercado Pago", "336": "C6 Bank", "341": "Itaú",
    "364": "Efí", "380": "PicPay", "399": "HSBC", "403": "Cora",
    "422": "Safra", "655": "Votorantim", "745": "Citibank",
    "748": "Sicredi", "756": "Sicoob",
}

# segmento da conta de consumo (2º dígito) -> categoria sugerida
_SEGMENTOS = {
    "1": ("Prefeitura", "Impostos"),
    "2": ("Saneamento (água)", "Água"),
    "3": ("Energia elétrica / gás", "Energia"),
    "4": ("Telecomunicações", "Internet / Telefone"),
    "5": ("Órgão do governo", "Impostos"),
    "6": ("Carnê / empresa", None),
    "7": ("Multa de trânsito", "Impostos"),
    "9": ("Uso exclusivo do banco", None),
}

_BASE_FATOR_ANTIGA = date(1997, 10, 7)
# o fator chegou a 9999 em 21/02/2025 e voltou pra 1000 em 22/02/2025
_BASE_FATOR_NOVA = date(2025, 2, 22)


class BoletoInvalidoError(ValueError):
    pass


def _so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def _mod10(numero: str) -> int:
    soma = 0
    peso = 2
    for digito in reversed(numero):
        parcial = int(digito) * peso
        soma += parcial // 10 + parcial % 10
        peso = 1 if peso == 2 else 2
    return (10 - soma % 10) % 10


def _mod11_bancario(numero: str) -> int:
    """DV geral do boleto bancário: pesos 2..9, resultado 0/10/11 -> 1."""
    soma = 0
    peso = 2
    for digito in reversed(numero):
        soma += int(digito) * peso
        peso = 2 if peso == 9 else peso + 1
    dv = 11 - soma % 11
    return 1 if dv in (0, 10, 11) else dv


def _mod11_arrecadacao(numero: str) -> int:
    soma = 0
    peso = 2
    for digito in reversed(numero):
        soma += int(digito) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    if resto in (0, 1):
        return 0
    if resto == 10:
        return 1
    return 11 - resto


def vencimento_pelo_fator(fator: str, hoje: date | None = None) -> date | None:
    """Fator 0000 = sem vencimento. Como o fator recomeçou em 2025, o
    mesmo número aponta pra duas datas -- vale a mais perto de hoje."""

    numero = int(fator)
    if numero == 0:
        return None

    hoje = hoje or date.today()
    antiga = _BASE_FATOR_ANTIGA + timedelta(days=numero)
    nova = _BASE_FATOR_NOVA + timedelta(days=numero - 1000) if numero >= 1000 else None

    if nova is None:
        return antiga
    return min((antiga, nova), key=lambda d: abs((d - hoje).days))


def chave_beneficiario(banco: str, campo_livre: str) -> str | None:
    """Pedaço do campo livre que identifica QUEM recebe (agência/conta
    ou código do beneficiário) e não muda de um boleto pro outro -- é com
    isso que o sistema lembra o fornecedor de um boleto em papel. Só pros
    bancos de layout conhecido; nos outros devolve None (sem aprender)."""

    cl = campo_livre
    if len(cl) != 25:
        return None

    if banco == "237":   # agência(4) carteira(2) nosso nº(11) conta(7) 0
        return f"237:{cl[0:4]}{cl[17:24]}"
    if banco == "341":   # carteira(3) nosso nº(8) dac agência(4) conta(5) dac 000
        return f"341:{cl[12:21]}"
    if banco == "033":   # 9 código beneficiário(7) nosso nº(13) IOS carteira(3)
        return f"033:{cl[1:8]}"
    if banco == "104":   # código beneficiário(6) DV ...
        return f"104:{cl[0:6]}"
    if banco == "756":   # carteira cooperativa(4) modalidade(2) cliente(7) ...
        return f"756:{cl[1:5]}{cl[7:14]}"
    if banco == "748":   # tipo carteira nosso nº(9) cooperativa(4) posto(2) código(5) ...
        return f"748:{cl[11:22]}"
    if banco == "001":   # convênio de 7 dígitos começa com 000000; senão 6 dígitos
        return f"001:{cl[6:13]}" if cl.startswith("000000") else f"001:{cl[0:6]}"
    return None


def _ler_bancario(digitos: str, hoje: date | None) -> dict:

    if len(digitos) == 47:
        campos = [(digitos[0:9], digitos[9]), (digitos[10:20], digitos[20]), (digitos[21:31], digitos[31])]
        for numero, dv in campos:
            if _mod10(numero) != int(dv):
                raise BoletoInvalidoError(
                    "O código do boleto tem um número errado. Confira se "
                    "foi digitado certinho."
                )
        barras = (
            digitos[0:4] + digitos[32] + digitos[33:47]
            + digitos[4:9] + digitos[10:20] + digitos[21:31]
        )
    else:
        barras = digitos

    if _mod11_bancario(barras[0:4] + barras[5:44]) != int(barras[4]):
        raise BoletoInvalidoError(
            "O código do boleto tem um número errado. Confira se foi "
            "digitado ou lido certinho."
        )

    banco = barras[0:3]
    campo_livre = barras[19:44]
    valor = (Decimal(int(barras[9:19])) / 100).quantize(Decimal("0.01"))

    linha = _linha_bancaria(barras)

    return {
        "tipo": "BANCARIO",
        "codigo_barras": barras,
        "linha_digitavel": linha,
        "banco_codigo": banco,
        "banco_nome": BANCOS.get(banco),
        "valor": valor if valor > 0 else None,
        "vencimento": vencimento_pelo_fator(barras[5:9], hoje),
        "segmento": None,
        "categoria_sugerida": None,
        "chave_beneficiario": chave_beneficiario(banco, campo_livre),
    }


def _linha_bancaria(barras: str) -> str:
    c1 = barras[0:4] + barras[19:24]
    c2 = barras[24:34]
    c3 = barras[34:44]
    return (
        f"{c1[:5]}.{c1[5:]}{_mod10(c1)} "
        f"{c2[:5]}.{c2[5:]}{_mod10(c2)} "
        f"{c3[:5]}.{c3[5:]}{_mod10(c3)} "
        f"{barras[4]} {barras[5:19]}"
    )


def _ler_arrecadacao(digitos: str, hoje: date | None) -> dict:

    identificador = digitos[2]
    if identificador not in "6789":
        raise BoletoInvalidoError("Código de conta de consumo inválido.")

    calcular = _mod10 if identificador in "67" else _mod11_arrecadacao

    if len(digitos) == 48:
        blocos = [digitos[i:i + 12] for i in range(0, 48, 12)]
        for bloco in blocos:
            if calcular(bloco[:11]) != int(bloco[11]):
                raise BoletoInvalidoError(
                    "O código da conta tem um número errado. Confira se "
                    "foi digitado certinho."
                )
        barras = "".join(b[:11] for b in blocos)
    else:
        barras = digitos

    if calcular(barras[0:3] + barras[4:44]) != int(barras[3]):
        raise BoletoInvalidoError(
            "O código da conta tem um número errado. Confira se foi "
            "digitado ou lido certinho."
        )

    # 6/7: valor de verdade; 8/9: valor de referência (não é o a pagar)
    valor = (Decimal(int(barras[4:15])) / 100).quantize(Decimal("0.01")) if identificador in "68" else None
    segmento = barras[1]
    nome_segmento, categoria = _SEGMENTOS.get(segmento, (None, None))

    # muitas concessionárias põem o vencimento AAAAMMDD logo depois da
    # identificação da empresa -- não é padrão, então só vale se for uma
    # data que faz sentido
    vencimento = None
    try:
        candidato = date(int(barras[19:23]), int(barras[23:25]), int(barras[25:27]))
        referencia = hoje or date.today()
        if abs((candidato - referencia).days) <= 120:
            vencimento = candidato
    except ValueError:
        pass

    linha = " ".join(
        f"{barras[i:i + 11]}-{calcular(barras[i:i + 11])}" for i in range(0, 44, 11)
    )

    return {
        "tipo": "ARRECADACAO",
        "codigo_barras": barras,
        "linha_digitavel": linha,
        "banco_codigo": None,
        "banco_nome": None,
        "valor": valor if valor else None,
        "vencimento": vencimento,
        "segmento": nome_segmento,
        "categoria_sugerida": categoria,
        # empresa (4 dígitos; CNPJ-8 no segmento 6) identifica quem cobra
        "chave_beneficiario": f"arrec:{segmento}:{barras[15:23] if segmento == '6' else barras[15:19]}",
    }


def ler_codigo(texto: str, hoje: date | None = None) -> dict:
    """Linha digitável (47 ou 48 dígitos) ou código de barras (44),
    com ou sem pontos/espaços."""

    digitos = _so_digitos(texto)

    if len(digitos) not in (44, 47, 48):
        raise BoletoInvalidoError(
            "Código incompleto: o boleto tem 47 números (conta de luz, água "
            "e telefone têm 48)."
        )

    if digitos[0] == "8" and len(digitos) in (44, 48):
        return _ler_arrecadacao(digitos, hoje)

    if len(digitos) == 48:
        raise BoletoInvalidoError("Código de conta de consumo inválido.")

    return _ler_bancario(digitos, hoje)


# ==================================================
# PDF
# ==================================================

_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_SEQUENCIA_CODIGO = re.compile(r"[\d][\d .\-]{42,70}\d")
_ROTULO_BENEFICIARIO = re.compile(r"(benefici[aá]rio|cedente)", re.IGNORECASE)
_LIXO_NOME = re.compile(
    r"(cnpj|cpf|ag[eê]ncia|c[oó]digo|benefici[aá]rio|cedente|final|endere[cç]o)"
    r"[^A-Za-zÀ-ú]*.*$",
    re.IGNORECASE,
)


def texto_do_pdf(conteudo: bytes) -> str:
    import io

    from pypdf import PdfReader

    try:
        leitor = PdfReader(io.BytesIO(conteudo))
        return "\n".join((pagina.extract_text() or "") for pagina in leitor.pages[:3])
    except Exception as e:
        raise BoletoInvalidoError(f"Não foi possível ler esse PDF ({e}).")


def _limpar_nome(trecho: str) -> str:
    trecho = _CNPJ.sub("", trecho)
    trecho = _LIXO_NOME.sub("", trecho)
    trecho = re.sub(r"[\s:\-–|]+$", "", re.sub(r"^[\s:\-–|]+", "", trecho))
    return re.sub(r"\s{2,}", " ", trecho).strip()


def beneficiario_do_texto(texto: str) -> tuple[str | None, str | None]:
    """(nome, cnpj) do beneficiário, lendo perto do rótulo
    "Beneficiário"/"Cedente". Boleto não tem layout fixo, então é
    melhor esforço -- quem confere é a pessoa, na tela."""

    linhas = [l.strip() for l in texto.splitlines()]

    for i, linha in enumerate(linhas):

        achou = _ROTULO_BENEFICIARIO.search(linha)
        if not achou:
            continue

        janela = " ".join(linhas[i:i + 3])
        cnpj_achado = _CNPJ.search(janela)
        cnpj = re.sub(r"\D", "", cnpj_achado.group()) if cnpj_achado else None

        candidatos = [linha[achou.end():]] + linhas[i + 1:i + 3]
        for candidato in candidatos:
            nome = _limpar_nome(candidato)
            if len(re.sub(r"[^A-Za-zÀ-ú]", "", nome)) >= 3:
                return nome[:110], cnpj

        if cnpj:
            return None, cnpj

    return None, None


def _codigo_dentro(digitos: str, hoje: date | None):
    """O código pode vir colado em outros números da mesma linha (ex.:
    "237-2 23790.12345..." -- o código do banco antes): tenta cada
    posição; os dígitos verificadores barram o que não é código."""
    for tamanho in (47, 48, 44):
        for inicio in range(len(digitos) - tamanho + 1):
            try:
                return ler_codigo(digitos[inicio:inicio + tamanho], hoje)
            except BoletoInvalidoError:
                continue
    return None


def ler_pdf(conteudo: bytes, hoje: date | None = None) -> dict:
    texto = texto_do_pdf(conteudo)

    resultado = None
    for trecho in _SEQUENCIA_CODIGO.findall(texto):
        resultado = _codigo_dentro(_so_digitos(trecho), hoje)
        if resultado:
            break

    nome, cnpj = beneficiario_do_texto(texto)

    if resultado is None:
        if not nome:
            raise BoletoInvalidoError(
                "Não achei o código do boleto nesse PDF. Digite ou bipe o "
                "código de barras."
            )
        resultado = {
            "tipo": None, "codigo_barras": None, "linha_digitavel": None,
            "banco_codigo": None, "banco_nome": None, "valor": None,
            "vencimento": None, "segmento": None, "categoria_sugerida": None,
            "chave_beneficiario": None,
        }

    resultado["beneficiario_nome"] = nome
    resultado["beneficiario_cnpj"] = cnpj
    return resultado
