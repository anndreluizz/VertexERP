from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.movimento_fiado import MovimentoFiado


class MovimentoFiadoRepository:

    @staticmethod
    def criar(db: Session, movimento: MovimentoFiado):
        db.add(movimento)
        db.commit()
        db.refresh(movimento)
        return movimento

    @staticmethod
    def listar(db: Session):
        return (
            db.query(MovimentoFiado)
            .order_by(MovimentoFiado.data.desc())
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, movimento_id: int):
        return (
            db.query(MovimentoFiado)
            .filter(MovimentoFiado.id == movimento_id)
            .first()
        )

    @staticmethod
    def listar_por_cliente(db: Session, cliente_id: int):
        return (
            db.query(MovimentoFiado)
            .filter(MovimentoFiado.cliente_id == cliente_id)
            .order_by(MovimentoFiado.data)
            .all()
        )

    @staticmethod
    def saldo_por_cliente(db: Session, cliente_id: int) -> float:
        valor_assinado = case(
            (MovimentoFiado.tipo == "COMPRA", MovimentoFiado.valor),
            else_=-MovimentoFiado.valor,
        )

        saldo = (
            db.query(func.sum(valor_assinado))
            .filter(MovimentoFiado.cliente_id == cliente_id)
            .scalar()
        )

        return saldo or 0.0
