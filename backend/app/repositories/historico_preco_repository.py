from sqlalchemy.orm import Session

from app.models.historico_preco import HistoricoPreco


class HistoricoPrecoRepository:

    @staticmethod
    def criar(db: Session, historico: HistoricoPreco):
        db.add(historico)
        db.commit()
        db.refresh(historico)
        return historico

    @staticmethod
    def listar_por_produto(db: Session, produto_id: int):
        return (
            db.query(HistoricoPreco)
            .filter(HistoricoPreco.produto_id == produto_id)
            .order_by(HistoricoPreco.data.desc())
            .all()
        )
