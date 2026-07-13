from sqlalchemy.orm import Session

from app.models.fornecedor import Fornecedor


class FornecedorRepository:

    @staticmethod
    def criar(db: Session, fornecedor: Fornecedor):
        db.add(fornecedor)
        db.commit()
        db.refresh(fornecedor)
        return fornecedor

    @staticmethod
    def listar(db: Session):
        return db.query(Fornecedor).all()

    @staticmethod
    def buscar_por_id(db: Session, fornecedor_id: int):
        return db.query(Fornecedor).filter(
            Fornecedor.id == fornecedor_id
        ).first()

    @staticmethod
    def atualizar(db: Session):
        db.commit()

    @staticmethod
    def excluir(db: Session, fornecedor: Fornecedor):
        db.delete(fornecedor)
        db.commit()