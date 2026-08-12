from sqlalchemy.orm import Session

from app.models.conta_pagar_evento import ContaPagarEvento
from app.repositories.conta_pagar_evento_repository import (
    ContaPagarEventoRepository,
)


class ContaPagarEventoService:

    @staticmethod
    def registrar(
        db: Session,
        conta_pagar_id: int,
        tipo: str,
        usuario_id: int | None = None,
        dispositivo: str | None = None,
        detalhes: str | None = None,
    ):
        evento = ContaPagarEvento(
            conta_pagar_id=conta_pagar_id,
            tipo=tipo,
            usuario_id=usuario_id,
            dispositivo=dispositivo,
            detalhes=detalhes,
        )

        return ContaPagarEventoRepository.criar(db, evento)

    @staticmethod
    def listar_por_conta(db: Session, conta_pagar_id: int):
        return ContaPagarEventoRepository.listar_por_conta(
            db, conta_pagar_id
        )
