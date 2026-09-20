from sqlalchemy.orm import Session

from app.models.plano_conta import PlanoConta


class PlanoContaRepository:

    @staticmethod
    def criar(db: Session, conta: PlanoConta):
        db.add(conta)
        db.commit()
        db.refresh(conta)
        return conta

    @staticmethod
    def listar(db: Session):
        return (
            db.query(PlanoConta)
            .filter(PlanoConta.ativo.is_(True))
            .order_by(PlanoConta.tipo, PlanoConta.codigo, PlanoConta.nome)
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, conta_id: int):
        return (
            db.query(PlanoConta)
            .filter(PlanoConta.id == conta_id)
            .first()
        )

    @staticmethod
    def listar_filhos_ativos(db: Session, conta_pai_id: int):
        return (
            db.query(PlanoConta)
            .filter(
                PlanoConta.conta_pai_id == conta_pai_id,
                PlanoConta.ativo.is_(True),
            )
            .all()
        )

    @staticmethod
    def atualizar(db: Session, conta: PlanoConta):
        db.commit()
        db.refresh(conta)
        return conta
