from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.produto import Produto


class ProdutoRepository:

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100, loja_id: int | None = None):
        query = db.query(Produto)

        # so' entram produtos globais (loja_id NULL) e os exclusivos
        # DESSA loja -- produto exclusivo de outra loja nunca aparece
        # (ver Produto.loja_id)
        if loja_id is not None:
            query = query.filter(
                or_(Produto.loja_id.is_(None), Produto.loja_id == loja_id)
            )

        return (
            query
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