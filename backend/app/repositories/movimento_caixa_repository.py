from sqlalchemy.orm import Session

from app.models.caixa import Caixa
from app.models.movimento_caixa import MovimentoCaixa


class MovimentoCaixaRepository:

    @staticmethod
    def criar(db: Session, movimento: MovimentoCaixa):
        db.add(movimento)
        db.commit()
        db.refresh(movimento)
        return movimento

    @staticmethod
    def listar(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        loja_id: int | None = None,
        data_inicio=None,
    ):
        # MovimentoCaixa nao tem loja_id proprio -- so' da pra saber a
        # loja de um movimento pela loja do caixa que o gerou, entao o
        # filtro precisa de join com Caixa (ver Caixa.loja_id)
        query = db.query(MovimentoCaixa)

        if loja_id is not None:
            query = query.join(
                Caixa, MovimentoCaixa.caixa_id == Caixa.id
            ).filter(Caixa.loja_id == loja_id)

        if data_inicio is not None:
            query = query.filter(MovimentoCaixa.data >= data_inicio)

        return (
            query
            .order_by(MovimentoCaixa.data.desc())
            .offset(skip)
            .limit(limit)
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

    @staticmethod
    def listar_por_tipo(db: Session, tipo: str):
        return (
            db.query(MovimentoCaixa)
            .filter(MovimentoCaixa.tipo == tipo.upper())
            .order_by(MovimentoCaixa.data.desc())
            .all()
        )

