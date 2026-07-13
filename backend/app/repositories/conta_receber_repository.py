from sqlalchemy.orm import Session

from app.models.conta_receber import ContaReceber


class ContaReceberRepository:

    @staticmethod
    def criar(db: Session, conta: ContaReceber):
        db.add(conta)
        db.commit()
        db.refresh(conta)
        return conta

    @staticmethod
    def listar(db: Session):
        return (
            db.query(ContaReceber)
            .order_by(ContaReceber.id.desc())
            .all()
        )

    @staticmethod
    def buscar_por_id(
        db: Session,
        conta_id: int
    ):
        return (
            db.query(ContaReceber)
            .filter(ContaReceber.id == conta_id)
            .first()
        )

    @staticmethod
    def listar_por_cliente(
        db: Session,
        cliente_id: int
    ):
        return (
            db.query(ContaReceber)
            .filter(
                ContaReceber.cliente_id == cliente_id
            )
            .order_by(
                ContaReceber.data_vencimento
            )
            .all()
        )

    @staticmethod
    def listar_pendentes(db: Session):
        return (
            db.query(ContaReceber)
            .filter(
                ContaReceber.status == "PENDENTE"
            )
            .order_by(
                ContaReceber.data_vencimento
            )
            .all()
        )

    @staticmethod
    def listar_recebidas(db: Session):
        return (
            db.query(ContaReceber)
            .filter(
                ContaReceber.status == "RECEBIDO"
            )
            .order_by(
                ContaReceber.data_recebimento.desc()
            )
            .all()
        )

    @staticmethod
    def atualizar(
        db: Session,
        conta: ContaReceber
    ):
        db.commit()
        db.refresh(conta)
        return conta

    @staticmethod
    def excluir(
        db: Session,
        conta: ContaReceber
    ):
        db.delete(conta)
        db.commit()