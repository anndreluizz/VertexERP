from sqlalchemy.orm import Session

from app.models.transacao_bancaria import TransacaoBancaria


class TransacaoBancariaRepository:

    @staticmethod
    def criar(db: Session, transacao: TransacaoBancaria):
        db.add(transacao)
        db.commit()
        db.refresh(transacao)
        return transacao

    @staticmethod
    def criar_lote(db: Session, transacoes: list[TransacaoBancaria]):
        db.add_all(transacoes)
        db.commit()
        return transacoes

    @staticmethod
    def buscar_por_id(db: Session, transacao_id: int):
        return (
            db.query(TransacaoBancaria)
            .filter(TransacaoBancaria.id == transacao_id)
            .first()
        )

    @staticmethod
    def fitids_existentes(
        db: Session, fitids: list[str], loja_id: int | None
    ) -> set[str]:
        if not fitids:
            return set()

        linhas = (
            db.query(TransacaoBancaria.fitid)
            .filter(
                TransacaoBancaria.fitid.in_(fitids),
                TransacaoBancaria.loja_id == loja_id,
            )
            .all()
        )
        return {fitid for (fitid,) in linhas}

    @staticmethod
    def listar(
        db: Session,
        loja_id: int | None = None,
        status: str | None = None,
    ):
        query = db.query(TransacaoBancaria)

        if loja_id is not None:
            query = query.filter(TransacaoBancaria.loja_id == loja_id)

        if status is not None:
            query = query.filter(TransacaoBancaria.status == status)

        return query.order_by(TransacaoBancaria.data.desc()).all()

    @staticmethod
    def atualizar(db: Session, transacao: TransacaoBancaria):
        db.commit()
        db.refresh(transacao)
        return transacao
