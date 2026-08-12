from sqlalchemy.orm import Session

from app.models.produto import Produto


class ProdutoRepository:

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return (
            db.query(Produto)
            .order_by(Produto.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, produto_id: int):
        return db.query(Produto).filter(
            Produto.id == produto_id
        ).first()

    @staticmethod
    def criar(db: Session, produto: Produto):
        db.add(produto)
        db.commit()
        db.refresh(produto)
        return produto

    @staticmethod
    def atualizar(db: Session, produto: Produto):
        db.commit()
        db.refresh(produto)
        return produto

    @staticmethod
    def excluir(db: Session, produto: Produto):
        db.delete(produto)
        db.commit()