import threading
import time
from datetime import date, timedelta

from sqlalchemy import func

from app.database.session import SessionLocal
from app.enums.status_conta_pagar import StatusContaPagar
from app.models.conta_pagar import ContaPagar
from app.services.notificacao_service import NotificacaoService

# 24h -- roda uma vez por dia, nao precisa de nada mais fino que isso
# pra um aviso de vencimento.
_INTERVALO_SEGUNDOS = 24 * 60 * 60


def _moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "_").replace(".", ",").replace(
        "_", "."
    )


def verificar_vencimentos_e_notificar(db) -> None:
    """Um push resumido (nao um por despesa, pra nao floodar o
    gerente) quando ha contas vencidas ou vencendo amanha. Pensada pra
    rodar uma vez por dia (ver iniciar_verificacao_diaria)."""

    hoje = date.today()
    amanha = hoje + timedelta(days=1)

    vencidas_qtd, vencidas_valor = (
        db.query(
            func.count(ContaPagar.id),
            func.coalesce(func.sum(ContaPagar.valor), 0),
        )
        .filter(
            ContaPagar.status == StatusContaPagar.PENDENTE.value,
            func.date(ContaPagar.data_vencimento) < hoje,
        )
        .one()
    )

    if vencidas_qtd:
        NotificacaoService.enviar_para_admins(
            db,
            "Contas vencidas",
            f"{vencidas_qtd} conta(s) vencida(s) — "
            f"{_moeda(float(vencidas_valor))}",
        )

    vencendo_qtd, vencendo_valor = (
        db.query(
            func.count(ContaPagar.id),
            func.coalesce(func.sum(ContaPagar.valor), 0),
        )
        .filter(
            ContaPagar.status == StatusContaPagar.PENDENTE.value,
            func.date(ContaPagar.data_vencimento) == amanha,
        )
        .one()
    )

    if vencendo_qtd:
        NotificacaoService.enviar_para_admins(
            db,
            "Contas vencendo amanhã",
            f"{vencendo_qtd} conta(s) vencendo amanhã — "
            f"{_moeda(float(vencendo_valor))}",
        )


def _loop() -> None:
    while True:
        db = SessionLocal()
        try:
            verificar_vencimentos_e_notificar(db)
        except Exception:
            # aviso e complemento -- uma falha aqui (banco fora do ar
            # num instante, Firebase indisponivel etc.) nao pode
            # derrubar a thread nem o backend.
            pass
        finally:
            db.close()

        time.sleep(_INTERVALO_SEGUNDOS)


def iniciar_verificacao_diaria() -> None:
    """Chamado uma vez no startup do FastAPI (ver main.py) -- dispara
    a primeira checagem quase na hora, depois repete a cada 24h numa
    thread em segundo plano (daemon: nao impede o processo de encerrar
    normalmente)."""

    threading.Thread(target=_loop, daemon=True).start()
