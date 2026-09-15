from sqlalchemy.orm import Session

from app.models.loja import Loja


class LojaRepository:

    @staticmethod
    def criar(db: Session, loja: Loja):
        db.add(loja)
        db.commit()
        db.refresh(loja)
        return loja

    @staticmethod
    def listar(db: Session):
        return db.query(Loja).order_by(Loja.id).all()

    @staticmethod
    def buscar_por_id(db: Session, loja_id: int):
        return db.query(Loja).filter(Loja.id == loja_id).first()

    @staticmethod
    def buscar_por_nome(db: Session, nome: str):
        return db.query(Loja).filter(Loja.nome == nome).first()
