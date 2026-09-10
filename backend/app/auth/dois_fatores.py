"""Segundo fator de autenticação (2FA) por código enviado por e-mail.

Depois que a senha é validada, se o usuário tiver dois_fatores_ativo,
o login NÃO devolve os tokens ainda -- gera um código de 6 dígitos,
manda por e-mail (reaproveitando o SMTP já configurado em
Configurações) e devolve só um "verificacao_id" opaco. Os tokens de
verdade só saem depois de POST /auth/verificar-2fa com esse
verificacao_id + o código certo.

Guardado em memória (mesmo raciocínio do app/auth/rate_limit.py: o
backend empacotado roda com uvicorn single-process/single-worker,
então não precisa de Redis/banco pra isso) -- cada entrada expira
sozinha e tem um limite de tentativas, pra não virar um jeito de
forçar o código por tentativa e erro.
"""

import secrets
from datetime import datetime, timedelta

VALIDADE = timedelta(minutes=10)
MAX_TENTATIVAS = 5

# verificacao_id -> {"usuario_id", "codigo", "expira_em", "tentativas"}
_pendentes: dict[str, dict] = {}


def _agora():
    return datetime.utcnow()


def gerar_codigo() -> str:
    """6 dígitos, com zero à esquerda quando precisar (ex.: '004821')."""
    return f"{secrets.randbelow(1_000_000):06d}"


def criar_pendente(usuario_id: int) -> tuple[str, str]:
    """Cria uma verificação pendente pro usuário e devolve
    (verificacao_id, codigo) -- quem chama é responsável por mandar o
    código pro usuário (e-mail); o verificacao_id é o que volta pro
    cliente."""

    _limpar_expirados()

    verificacao_id = secrets.token_urlsafe(32)
    codigo = gerar_codigo()

    _pendentes[verificacao_id] = {
        "usuario_id": usuario_id,
        "codigo": codigo,
        "expira_em": _agora() + VALIDADE,
        "tentativas": 0,
    }

    return verificacao_id, codigo


def verificar(verificacao_id: str, codigo: str) -> int | None:
    """Confere o código contra a verificação pendente. Devolve o
    usuario_id em caso de sucesso (e remove a entrada, um código só
    vale uma vez), ou None se o verificacao_id não existir/já tiver
    expirado/esgotado as tentativas/o código não bater. Cada chamada
    com código errado conta como uma tentativa, mesmo em verificacoes
    ainda válidas -- depois de MAX_TENTATIVAS a entrada é descartada
    (força um novo login do zero, com um código novo)."""

    pendente = _pendentes.get(verificacao_id)

    if not pendente:
        return None

    if _agora() > pendente["expira_em"]:
        del _pendentes[verificacao_id]
        return None

    pendente["tentativas"] += 1

    if pendente["tentativas"] > MAX_TENTATIVAS:
        del _pendentes[verificacao_id]
        return None

    # compare_digest evita side-channel por tempo de comparação --
    # pouco relevante pra um codigo de 6 digitos com poucas tentativas
    # permitidas, mas e de graca e e o jeito certo de comparar segredo.
    if not secrets.compare_digest(pendente["codigo"], codigo.strip()):
        return None

    usuario_id = pendente["usuario_id"]
    del _pendentes[verificacao_id]

    return usuario_id


def _limpar_expirados():
    agora = _agora()
    expirados = [
        vid for vid, dados in _pendentes.items() if agora > dados["expira_em"]
    ]
    for vid in expirados:
        del _pendentes[vid]
