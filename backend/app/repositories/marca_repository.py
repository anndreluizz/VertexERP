from sqlalchemy.orm import Session

from app.models.marca import Marca


class MarcaRepository:

    @staticmethod
    def criar(db: Session, marca: Marca):
        db.add(marca)
        db.commit()
        db.refresh(marca)
        return marca

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return (
            db.query(Marca)
            .order_by(Marca.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, marca_id: int):
        return db.query(Marca).filter(
            Marca.id == marca_id
        ).first()

    @staticmethod
    def buscar_por_nome(db: Session, nome: str):
        return db.query(Marca).filter(
            Marca.nome == nome
        ).first()

    @staticmethod
    def atualizar(db: Session, marca: Marca):
        db.commit()
        db.refresh(marca)
        return marca

    @staticmethod
    def excluir(db: Session, marca: Marca):
        db.delete(marca)
        db.commit()
