from sqlalchemy.orm import Session

from app.models.conta_pagar_evento import ContaPagarEvento


class ContaPagarEventoRepository:

    @staticmethod
    def criar(db: Session, evento: ContaPagarEvento):
        db.add(evento)
        db.commit()
        db.refresh(evento)
        return evento

    @staticmethod
    def listar_por_conta(db: Session, conta_pagar_id: int):
        return (
            db.query(ContaPagarEvento)
            .filter(ContaPagarEvento.conta_pagar_id == conta_pagar_id)
            .order_by(ContaPagarEvento.data)
            .all()
        )
