from sqlalchemy.orm import Session

from app.models.movimento_caixa import MovimentoCaixa


class MovimentoCaixaRepository:

    @staticmethod
    def criar(db: Session, movimento: MovimentoCaixa):
        db.add(movimento)
        db.commit()
        db.refresh(movimento)
        return movimento

    @staticmethod
    def listar(db: Session):
        return (
            db.query(MovimentoCaixa)
            .order_by(MovimentoCaixa.data.desc())
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, movimento_id: int):
        return (
            db.query(MovimentoCaixa)
            .filter(MovimentoCaixa.id == movimento_id)
            .first()
        )

    @staticmethod
    def listar_por_caixa(db: Session, caixa_id: int):
        return (
            db.query(MovimentoCaixa)
            .filter(MovimentoCaixa.caixa_id == caixa_id)
            .order_by(MovimentoCaixa.data.desc())
            .all()
        )

