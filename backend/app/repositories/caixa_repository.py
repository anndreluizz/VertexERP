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
    def buscar_aberto(db: Session, usuario_id: int, loja_id: int | None = None):
        # loja_id filtra o caixa aberto pela loja alem do usuario -- sem
        # isso, um admin com caixa aberto na Matriz nao conseguiria abrir
        # (nem operar) um caixa separado na Filial, porque o sistema
        # acharia que ele "ja tem caixa aberto" (o da outra loja)
        query = (
            db.query(Caixa)
            .filter(Caixa.status == "ABERTO")
            .filter(Caixa.usuario_id == usuario_id)
        )

        if loja_id is not None:
            query = query.filter(Caixa.loja_id == loja_id)

        return query.first()

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