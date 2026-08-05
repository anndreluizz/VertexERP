from sqlalchemy.orm import Session

from app.models.solicitacao_aprovacao import SolicitacaoAprovacao


class SolicitacaoAprovacaoRepository:

    @staticmethod
    def criar(db: Session, solicitacao: SolicitacaoAprovacao):
        db.add(solicitacao)
        db.commit()
        db.refresh(solicitacao)
        return solicitacao

    @staticmethod
    def buscar_por_id(db: Session, solicitacao_id: int):
        return (
            db.query(SolicitacaoAprovacao)
            .filter(SolicitacaoAprovacao.id == solicitacao_id)
            .first()
        )

    @staticmethod
    def listar_pendentes(db: Session):
        return (
            db.query(SolicitacaoAprovacao)
            .filter(SolicitacaoAprovacao.status == "PENDENTE")
            .order_by(SolicitacaoAprovacao.criado_em.desc())
            .all()
        )

    @staticmethod
    def atualizar(db: Session, solicitacao: SolicitacaoAprovacao):
        db.commit()
        db.refresh(solicitacao)
        return solicitacao
