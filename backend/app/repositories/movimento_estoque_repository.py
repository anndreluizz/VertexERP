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
    def listar(db: Session):
        return (
            db.query(MovimentoEstoque)
            .order_by(MovimentoEstoque.data.desc())
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, movimento_id: int):
        return (
            db.query(MovimentoEstoque)
            .filter(MovimentoEstoque.id == movimento_id)
            .first()
        )

    @staticmethod
    def listar_por_produto(db: Session, produto_id: int):
        return (
            db.query(MovimentoEstoque)
            .filter(MovimentoEstoque.produto_id == produto_id)
            .order_by(MovimentoEstoque.data.desc())
            .all()
        )
