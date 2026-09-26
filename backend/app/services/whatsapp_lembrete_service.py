import threading
import time
from datetime import datetime

from app.database.session import SessionLocal
from app.models.cliente import Cliente
from app.repositories.movimento_fiado_repository import MovimentoFiadoRepository
from app.services.configuracao_service import ConfiguracaoService
from app.services.whatsapp_service import WhatsappService

# 24h -- mesmo intervalo do aviso_vencimento_service.py, roda uma vez
# por dia.
_INTERVALO_SEGUNDOS = 24 * 60 * 60


def _moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "_").replace(".", ",").replace(
        "_", "."
    )


def _primeiro_nome(nome: str) -> str:
    return (nome or "").strip().split(" ")[0] or nome


def verificar_fiados_parados_e_notificar(db) -> None:
    """Manda um lembrete de WhatsApp pra cada cliente com saldo
    devedor em aberto ha mais de X dias sem nenhuma movimentacao
    (nem compra nem pagamento) -- pensada pra rodar uma vez por dia
    (ver iniciar_verificacao_diaria). So dispara se a integracao e o
    lembrete de fiado estiverem ligados em Configuracoes."""

    config = ConfiguracaoService.buscar(db)

    if not config.whatsapp_ativo or not config.whatsapp_lembrete_fiado_ativo:
        return

    dias_limite = config.whatsapp_lembrete_fiado_dias or 30

    parados = MovimentoFiadoRepository.listar_parados(db, dias_limite)

    agora = datetime.now()

    for cliente_id, saldo, _ultima_movimentacao in parados:

        if not saldo or saldo <= 0:
            continue

        cliente = (
            db.query(Cliente)
            .filter(Cliente.id == cliente_id, Cliente.ativo.is_(True))
            .first()
        )

        if not cliente or not cliente.telefone:
            continue

        # nao renotifica antes de completar o mesmo intervalo de dias
        # desde o ultimo aviso -- senao manda a mesma mensagem todo
        # dia enquanto o cliente nao pagar.
        if cliente.whatsapp_fiado_avisado_em:
            dias_desde_aviso = (
                agora - cliente.whatsapp_fiado_avisado_em
            ).days
            if dias_desde_aviso < dias_limite:
                continue

        texto = (
            f"Olá {_primeiro_nome(cliente.nome)}! Passando pra lembrar "
            f"que você tem um saldo em aberto de {_moeda(float(saldo))} "
            f"conosco. Quando puder, dá uma passadinha pra regularizar. "
            f"Obrigado! 🙂"
        )

        enviado = WhatsappService.enviar_mensagem(db, cliente.telefone, texto)

        if enviado:
            cliente.whatsapp_fiado_avisado_em = agora
            db.add(cliente)
            db.commit()


def _loop() -> None:
    while True:
        db = SessionLocal()
        try:
            verificar_fiados_parados_e_notificar(db)
        except Exception:
            # mesma filosofia do aviso_vencimento_service.py -- uma
            # falha aqui (banco fora do ar num instante, Z-API
            # indisponivel etc.) nao pode derrubar a thread nem o
            # backend.
            pass
        finally:
            db.close()

        time.sleep(_INTERVALO_SEGUNDOS)


def iniciar_verificacao_diaria() -> None:
    """Chamado uma vez no startup do FastAPI (ver main.py) -- dispara
    a primeira checagem quase na hora, depois repete a cada 24h numa
    thread em segundo plano (daemon: nao impede o processo de
    encerrar normalmente)."""

    threading.Thread(target=_loop, daemon=True).start()
