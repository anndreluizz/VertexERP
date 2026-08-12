from sqlalchemy.orm import Session

from app.models.categoria import Categoria


class CategoriaRepository:

    @staticmethod
    def criar(db: Session, categoria: Categoria):
        db.add(categoria)
        db.commit()
        db.refresh(categoria)
        return categoria

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return (
            db.query(Categoria)
            .order_by(Categoria.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, categoria_id: int):
        return db.query(Categoria).filter(
            Categoria.id == categoria_id
        ).first()

    @staticmethod
    def buscar_por_nome(db: Session, nome: str):
        return db.query(Categoria).filter(
            Categoria.nome == nome
        ).first()

    @staticmethod
    def atualizar(db: Session, categoria: Categoria):
        db.commit()
        db.refresh(categoria)
        return categoria

    @staticmethod
    def excluir(db: Session, categoria: Categoria):
        db.delete(categoria)
        db.commit()