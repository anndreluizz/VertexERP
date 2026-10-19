import threading
import time
from datetime import date, datetime, timedelta

from sqlalchemy import func

from app.database.session import SessionLocal
from app.enums.status_conta_pagar import StatusContaPagar
from app.models.conta_pagar import ContaPagar
from app.services.notificacao_service import NotificacaoService

# hora do aviso diario -- antes era "24h depois do backend ligar", o
# que caia em qualquer hora (ou antes de lancarem as contas do dia)
_HORA_AVISO = 8


def segundos_ate_proximo_aviso(agora: datetime) -> float:
    proximo = agora.replace(hour=_HORA_AVISO, minute=0, second=0, microsecond=0)
    if proximo <= agora:
        proximo += timedelta(days=1)
    return (proximo - agora).total_seconds()


def _moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "_").replace(".", ",").replace(
        "_", "."
    )


def verificar_vencimentos_e_notificar(db) -> None:
    """Um push resumido (nao um por despesa, pra nao floodar o
    gerente) quando ha contas vencidas, vencendo hoje ou amanha. Pensada pra
    rodar uma vez por dia (ver iniciar_verificacao_diaria)."""

    # contas fixas do mes: cria aqui tambem, pra elas entrarem no aviso
    # mesmo que ninguem tenha aberto Contas a Pagar ainda
    from app.services.conta_recorrente_service import ContaRecorrenteService

    ContaRecorrenteService.gerar_pendentes(db)

    hoje = date.today()
    amanha = hoje + timedelta(days=1)

    dia = func.date(ContaPagar.data_vencimento)
    avisos = [
        (dia < hoje, "Contas vencidas", "vencida(s)"),
        (dia == hoje, "Contas vencendo hoje", "vencendo hoje"),
        (dia == amanha, "Contas vencendo amanhã", "vencendo amanhã"),
    ]

    for filtro, titulo, texto in avisos:
        qtd, valor = (
            db.query(
                func.count(ContaPagar.id),
                func.coalesce(func.sum(ContaPagar.valor), 0),
            )
            .filter(ContaPagar.status == StatusContaPagar.PENDENTE.value, filtro)
            .one()
        )

        if qtd:
            NotificacaoService.enviar_para_admins(
                db,
                titulo,
                f"{qtd} conta(s) {texto} — {_moeda(float(valor))}",
            )

    # luz e parecidas: valor copiado do mes anterior que ninguem confirmou
    a_confirmar = (
        db.query(func.count(ContaPagar.id))
        .filter(
            ContaPagar.status == StatusContaPagar.PENDENTE.value,
            ContaPagar.valor_a_confirmar.is_(True),
        )
        .scalar()
    )

    if a_confirmar:
        NotificacaoService.enviar_para_admins(
            db,
            "Contas com valor a confirmar",
            f"{a_confirmar} conta(s) fixa(s) com o valor do mês passado. "
            "Quando a fatura chegar, corrija o valor em Contas a Pagar.",
        )


def _verificar() -> None:
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


def _loop() -> None:
    # ligou depois das 8h (PC ligado tarde, backend reiniciado): avisa
    # ja, senao o dia passaria sem aviso
    if datetime.now().hour >= _HORA_AVISO:
        _verificar()

    while True:
        time.sleep(segundos_ate_proximo_aviso(datetime.now()))
        _verificar()


def iniciar_verificacao_diaria() -> None:
    """Chamado uma vez no startup do FastAPI (ver main.py) -- checa
    todo dia as 8h (e na hora, se ligar depois das 8h) numa
    thread em segundo plano (daemon: nao impede o processo de encerrar
    normalmente)."""

    threading.Thread(target=_loop, daemon=True).start()
