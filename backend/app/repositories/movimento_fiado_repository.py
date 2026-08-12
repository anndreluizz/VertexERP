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
    def listar_por_cliente(db: Session, cliente_id: int):
        return (
            db.query(MovimentoFiado)
            .filter(MovimentoFiado.cliente_id == cliente_id)
            .order_by(MovimentoFiado.data)
            .all()
        )

    @staticmethod
    def total_devedor(db: Session):
        """Soma o saldo devedor de todos os clientes (só conta quem tem
        saldo positivo — cliente com crédito/pagou a mais não abate o
        total devido por outros)."""

        saldo_por_cliente = case(
            (MovimentoFiado.tipo == "COMPRA", MovimentoFiado.valor),
            else_=-MovimentoFiado.valor,
        )

        resultados = (
            db.query(func.sum(saldo_por_cliente))
            .group_by(MovimentoFiado.cliente_id)
            .all()
        )

        return sum(
            max(0.0, float(saldo))
            for (saldo,) in resultados
            if saldo is not None
        )

    @staticmethod
    def saldos_por_cliente(db: Session):
        """Retorna {cliente_id: saldo_devedor} para todo cliente que tem
        pelo menos um movimento de fiado (saldo pode ser negativo se o
        cliente pagou a mais)."""

        saldo_por_cliente = case(
            (MovimentoFiado.tipo == "COMPRA", MovimentoFiado.valor),
            else_=-MovimentoFiado.valor,
        )

        resultados = (
            db.query(
                MovimentoFiado.cliente_id,
                func.sum(saldo_por_cliente),
            )
            .group_by(MovimentoFiado.cliente_id)
            .all()
        )

        return {
            cliente_id: float(saldo)
            for cliente_id, saldo in resultados
            if saldo is not None
        }
