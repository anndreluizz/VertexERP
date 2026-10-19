from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.produto import Produto


class CategoriaRepository:

    @staticmethod
    def criar(db: Session, categoria: Categoria):
        db.add(categoria)
        db.commit()
        db.refresh(categoria)
        return categoria

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100, recentes: bool = False):
        ordem = [Categoria.id]
        if recentes:
            # cadastro de produto: a usada por ultimo primeiro (o produto
            # guarda a categoria pelo nome, sem id)
            ultimo_produto = (
                db.query(func.max(Produto.id))
                .filter(func.upper(Produto.categoria) == func.upper(Categoria.nome))
                .correlate(Categoria)
                .scalar_subquery()
            )
            ordem = [ultimo_produto.desc().nulls_last(), Categoria.nome]
        return (
            db.query(Categoria)
            .order_by(*ordem)
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