from sqlalchemy.orm import Session

from app.models.caixa import Caixa


class CaixaRepository:

    @staticmethod
    def criar(db: Session, caixa: Caixa):
        db.add(caixa)
        db.commit()
        db.refresh(caixa)
        return caixa

    @staticmethod
    def buscar_aberto(db: Session):
        return (
            db.query(Caixa)
            .filter(Caixa.status == "ABERTO")
            .first()
        )

    @staticmethod
    def atualizar(db: Session, caixa: Caixa):
        db.commit()
        db.refresh(caixa)
        return caixa