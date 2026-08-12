from sqlalchemy.orm import Session

from app.models.movimento_estoque import MovimentoEstoque


class MovimentoEstoqueRepository:

    @staticmethod
    def criar(db: Session, movimento: MovimentoEstoque):
        db.add(movimento)
        db.commit()
        db.refresh(movimento)
        return movimento

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return (
            db.query(MovimentoEstoque)
            .order_by(MovimentoEstoque.data.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def listar_por_produto(
        db: Session,
        produto_id: int,
        skip: int = 0,
        limit: int = 100,
    ):
        return (
            db.query(MovimentoEstoque)
            .filter(MovimentoEstoque.produto_id == produto_id)
            .order_by(MovimentoEstoque.data.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
