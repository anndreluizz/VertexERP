from sqlalchemy.orm import Session

from app.models.transferencia_estoque import TransferenciaEstoque


class TransferenciaEstoqueRepository:

    @staticmethod
    def criar(db: Session, transferencia: TransferenciaEstoque):
        db.add(transferencia)
        db.flush()
        return transferencia

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return (
            db.query(TransferenciaEstoque)
            .order_by(TransferenciaEstoque.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
