from sqlalchemy.orm import Session

from app.models.caixa import Caixa


class CaixaRepository:

    @staticmethod
    def criar(db: Session, caixa: Caixa):
        db.add(caixa)
        db.commit()
        db.refresh(caixa)
        return caixa

    @staticmethod
    def buscar_aberto(db: Session, usuario_id: int):
        return (
            db.query(Caixa)
            .filter(Caixa.status == "ABERTO")
            .filter(Caixa.usuario_id == usuario_id)
            .first()
        )

    @staticmethod
    def atualizar(db: Session, caixa: Caixa):
        db.commit()
        db.refresh(caixa)
        return caixa

    @staticmethod
    def listar(db: Session, limite: int = 20):
        return (
            db.query(Caixa)
            .order_by(Caixa.data_abertura.desc())
            .limit(limite)
            .all()
        )