from sqlalchemy.orm import Session

from app.models.conta_pagar import ContaPagar
from app.enums.status_conta_pagar import StatusContaPagar


class ContaPagarRepository:

    @staticmethod
    def criar(db: Session, conta: ContaPagar):
        db.add(conta)
        db.commit()
        db.refresh(conta)
        return conta

    @staticmethod
    def atualizar(db: Session, conta: ContaPagar):
        db.commit()
        db.refresh(conta)
        return conta

    @staticmethod
    def excluir(db: Session, conta: ContaPagar):
        db.delete(conta)
        db.commit()

    @staticmethod
    def buscar_por_id(
        db: Session,
        conta_id: int,
    ):
        return (
            db.query(ContaPagar)
            .filter(
                ContaPagar.id == conta_id
            )
            .first()
        )

    @staticmethod
    def listar(db: Session):
        return (
            db.query(ContaPagar)
            .order_by(
                ContaPagar.data_vencimento
            )
            .all()
        )

    @staticmethod
    def listar_pendentes(db: Session):
        return (
            db.query(ContaPagar)
            .filter(
                ContaPagar.status == StatusContaPagar.PENDENTE.value
            )
            .all()
        )

    @staticmethod
    def listar_pagas(db: Session):
        return (
            db.query(ContaPagar)
            .filter(
                ContaPagar.status == StatusContaPagar.PAGO.value
            )
            .all()
        )