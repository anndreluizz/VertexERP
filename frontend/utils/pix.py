"""Reconhece o que foi colado no campo Pix de uma conta: o Pix copia e
cola (BR Code, começa com 000201) ou uma chave Pix (CPF/CNPJ, telefone,
e-mail ou aleatória)."""

import re

_ALEATORIA = re.compile(r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$", re.I)


def _campos(texto):
    """BR Code é uma sequência de id (2 dígitos) + tamanho (2) + valor."""
    campos, i = {}, 0
    while i + 4 <= len(texto):
        ident, tamanho = texto[i:i + 2], texto[i + 2:i + 4]
        if not tamanho.isdigit():
            break
        campos[ident] = texto[i + 4:i + 4 + int(tamanho)]
        i += 4 + int(tamanho)
    return campos


def _cpf_valido(d):
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def _chave(texto):
    digitos = re.sub(r"\D", "", texto)
    if "@" in texto:
        return {"tipo": "chave", "tipo_chave": "E-mail", "copiar": texto}
    if _ALEATORIA.match(texto):
        return {"tipo": "chave", "tipo_chave": "Chave aleatória", "copiar": texto}
    if re.fullmatch(r"[\d.\-/]+", texto) and len(digitos) == 14:
        return {"tipo": "chave", "tipo_chave": "CNPJ", "copiar": digitos}
    telefone = texto.startswith("+") or "(" in texto
    if re.fullmatch(r"[\d.\-]+", texto) and _cpf_valido(digitos) and not telefone:
        return {"tipo": "chave", "tipo_chave": "CPF", "copiar": digitos}
    if re.fullmatch(r"[\d\s()+\-]+", texto) and 10 <= len(digitos) <= 13:
        if not digitos.startswith("55") or len(digitos) <= 11:
            digitos = "55" + digitos
        return {"tipo": "chave", "tipo_chave": "Telefone", "copiar": "+" + digitos}
    return {"tipo": "chave", "tipo_chave": "Chave Pix", "copiar": texto}


def ler_pix(texto):
    """None se vazio. Senão um dict com 'tipo' ('copia_e_cola' ou
    'chave') e 'copiar' (o texto pra colar no app do banco). Copia e
    cola traz também 'valor' (float ou None), 'nome' e 'cidade' do
    recebedor e a 'chave' dele quando vem no código."""

    texto = (texto or "").strip()
    if not texto:
        return None

    if not texto.startswith("000201"):
        return _chave(texto)

    campos = _campos(texto)
    chave = None
    for ident in range(26, 52):
        conta = _campos(campos.get(f"{ident:02d}", ""))
        if conta.get("00", "").lower() == "br.gov.bcb.pix":
            chave = conta.get("01")
            break
    try:
        valor = float(campos["54"]) if campos.get("54") else None
    except ValueError:
        valor = None
    return {
        "tipo": "copia_e_cola",
        "copiar": texto,
        "valor": valor,
        "nome": (campos.get("59") or "").strip() or None,
        "cidade": (campos.get("60") or "").strip() or None,
        "chave": chave,
    }


def texto_pra_copiar(pix):
    lido = ler_pix(pix)
    return lido["copiar"] if lido else None
