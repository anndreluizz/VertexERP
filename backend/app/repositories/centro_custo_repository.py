from sqlalchemy.orm import Session

from app.models.centro_custo import CentroCusto


class CentroCustoRepository:

    @staticmethod
    def criar(db: Session, centro: CentroCusto):
        db.add(centro)
        db.commit()
        db.refresh(centro)
        return centro

    @staticmethod
    def listar(db: Session):
        return (
            db.query(CentroCusto)
            .order_by(CentroCusto.nome)
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, centro_id: int):
        return (
            db.query(CentroCusto)
            .filter(CentroCusto.id == centro_id)
            .first()
        )

    @staticmethod
    def buscar_por_nome(db: Session, nome: str):
        return (
            db.query(CentroCusto)
            .filter(CentroCusto.nome == nome)
            .first()
        )

    @staticmethod
    def atualizar(db: Session, centro: CentroCusto):
        db.commit()
        db.refresh(centro)
        return centro

    @staticmethod
    def excluir(db: Session, centro: CentroCusto):
        db.delete(centro)
        db.commit()
