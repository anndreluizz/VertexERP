from sqlalchemy.orm import Session

from app.models.compra import Compra


class CompraRepository:

    @staticmethod
    def criar(
        db: Session,
        compra: Compra,
    ):
        db.add(compra)
        db.flush()
        return compra

    @staticmethod
    def salvar(db: Session):
        db.commit()

    @staticmethod
    def listar(db: Session):
        return (
            db.query(Compra)
            .all()
        )

    @staticmethod
    def buscar_por_id(
        db: Session,
        compra_id: int,
    ):
        return (
            db.query(Compra)
            .filter(
                Compra.id == compra_id
            )
            .first()
        )

    @staticmethod
    def excluir(
        db: Session,
        compra: Compra,
    ):
        db.delete(compra)
        db.commit()