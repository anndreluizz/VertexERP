"""Freio simples contra tentativa de senha por força bruta no login --
em memória mesmo (o backend roda num único processo, ver
backend_entry.py::uvicorn.run sem workers=), sem precisar de Redis
nem tabela nova no banco. Reinicia zerado se o servidor reiniciar --
tradeoff aceitável pra um sistema de loja de PC único/rede local, não
um serviço público exposto na internet."""

from collections import defaultdict
from datetime import datetime, timedelta

# poucas tentativas ruins de senha é normal (dedo trêmulo, teclado
# errado) -- 5 dentro de 15 minutos é generoso o bastante pra não
# irritar um caixa de verdade, mas já barra automação simples
MAX_TENTATIVAS = 5
JANELA = timedelta(minutes=15)
BLOQUEIO = timedelta(minutes=15)

# email (lowercase) -> lista de timestamps das falhas recentes
_falhas: dict[str, list[datetime]] = defaultdict(list)

# email (lowercase) -> até quando fica bloqueado
_bloqueados: dict[str, datetime] = {}


def _normalizar(email: str) -> str:
    return (email or "").strip().lower()


def segundos_ate_desbloquear(email: str) -> int:
    """0 = não está bloqueado. Caso contrário, quantos segundos faltam."""

    chave = _normalizar(email)
    ate = _bloqueados.get(chave)

    if not ate:
        return 0

    restante = (ate - datetime.utcnow()).total_seconds()

    if restante <= 0:
        # o bloqueio já venceu -- limpa pra não ficar checando de novo
        _bloqueados.pop(chave, None)
        _falhas.pop(chave, None)
        return 0

    return int(restante) + 1


def registrar_falha(email: str) -> None:

    chave = _normalizar(email)
    agora = datetime.utcnow()

    # descarta falhas fora da janela antes de contar -- senão 5
    # tentativas erradas espalhadas ao longo de dias iam se acumular
    # pra sempre e bloquear alguém que só errou de vez em quando
    _falhas[chave] = [
        t for t in _falhas[chave] if agora - t < JANELA
    ] + [agora]

    if len(_falhas[chave]) >= MAX_TENTATIVAS:
        _bloqueados[chave] = agora + BLOQUEIO


def limpar(email: str) -> None:
    """Chamado num login bem-sucedido -- zera o histórico de falhas."""

    chave = _normalizar(email)
    _falhas.pop(chave, None)
    _bloqueados.pop(chave, None)
