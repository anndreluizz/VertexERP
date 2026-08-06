from datetime import datetime

from sqlalchemy.orm import Session

from app.models.solicitacao_aprovacao import SolicitacaoAprovacao
from app.repositories.solicitacao_aprovacao_repository import (
    SolicitacaoAprovacaoRepository,
)
from app.services.notificacao_service import NotificacaoService

# Cada tipo novo de acao sensivel (reabertura de caixa, desconto acima
# do limite, etc.) so precisa de uma entrada nova aqui, apontando pra
# uma funcao que executa a acao de verdade quando aprovada — o resto
# do fluxo (pedir, notificar, aprovar/rejeitar) ja e generico.


def _executar_excluir_cliente(
    db: Session, referencia_id: int, aprovador_id: int | None = None,
):
    from app.services.cliente_service import ClienteService

    ClienteService.excluir(db, referencia_id)


def _executar_cancelar_conta_pagar(
    db: Session, referencia_id: int, aprovador_id: int | None = None,
):
    from app.services.conta_pagar_service import ContaPagarService

    ContaPagarService.cancelar(db, referencia_id, usuario_id=aprovador_id)


_EXECUTORES = {
    "EXCLUIR_CLIENTE": _executar_excluir_cliente,
    "CANCELAR_CONTA_PAGAR": _executar_cancelar_conta_pagar,
}


class AprovacaoService:

    @staticmethod
    def solicitar(
        db: Session,
        tipo: str,
        referencia_id: int,
        descricao: str,
        solicitante_id: int,
    ):
        solicitacao = SolicitacaoAprovacao(
            tipo=tipo,
            referencia_id=referencia_id,
            descricao=descricao,
            solicitante_id=solicitante_id,
        )

        solicitacao = SolicitacaoAprovacaoRepository.criar(
            db, solicitacao
        )

        NotificacaoService.enviar_para_admins(
            db,
            "Aprovação pendente",
            descricao,
            excluir_usuario_id=solicitante_id,
        )

        return solicitacao

    @staticmethod
    def listar_pendentes(db: Session):
        return SolicitacaoAprovacaoRepository.listar_pendentes(db)

    @staticmethod
    def aprovar(db: Session, solicitacao_id: int, aprovador_id: int):
        solicitacao = SolicitacaoAprovacaoRepository.buscar_por_id(
            db, solicitacao_id
        )

        if not solicitacao:
            raise Exception("Solicitação não encontrada.")

        if solicitacao.status != "PENDENTE":
            raise Exception("Essa solicitação já foi resolvida.")

        executor = _EXECUTORES.get(solicitacao.tipo)

        if executor is None:
            raise Exception(
                f"Tipo de solicitação desconhecido: {solicitacao.tipo}"
            )

        # roda a acao de verdade so depois de confirmar que a
        # solicitacao ainda era valida — se isso falhar, a solicitacao
        # continua PENDENTE (nao marca como aprovada por engano)
        executor(db, solicitacao.referencia_id, aprovador_id)

        solicitacao.status = "APROVADA"
        solicitacao.aprovador_id = aprovador_id
        solicitacao.resolvido_em = datetime.utcnow()

        solicitacao = SolicitacaoAprovacaoRepository.atualizar(
            db, solicitacao
        )

        NotificacaoService.enviar_para_usuario(
            db,
            solicitacao.solicitante_id,
            "Solicitação aprovada",
            solicitacao.descricao,
        )

        return solicitacao

    @staticmethod
    def rejeitar(db: Session, solicitacao_id: int, aprovador_id: int):
        solicitacao = SolicitacaoAprovacaoRepository.buscar_por_id(
            db, solicitacao_id
        )

        if not solicitacao:
            raise Exception("Solicitação não encontrada.")

        if solicitacao.status != "PENDENTE":
            raise Exception("Essa solicitação já foi resolvida.")

        solicitacao.status = "REJEITADA"
        solicitacao.aprovador_id = aprovador_id
        solicitacao.resolvido_em = datetime.utcnow()

        solicitacao = SolicitacaoAprovacaoRepository.atualizar(
            db, solicitacao
        )

        NotificacaoService.enviar_para_usuario(
            db,
            solicitacao.solicitante_id,
            "Solicitação rejeitada",
            solicitacao.descricao,
        )

        return solicitacao
