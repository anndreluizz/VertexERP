from sqlalchemy.orm import Session

from app.models.venda import Venda


class VendaRepository:

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100, loja_id: int | None = None):
        # mais recente primeiro -- pra "carregar mais" na tela de
        # vendas mostrar o historico atual logo na primeira pagina,
        # em vez de comecar pelas vendas mais antigas
        query = db.query(Venda)

        if loja_id is not None:
            query = query.filter(Venda.loja_id == loja_id)

        return (
            query
            .order_by(Venda.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, venda_id: int):
        return (
            db.query(Venda)
            .filter(Venda.id == venda_id)
            .first()
        )

    @staticmethod
    def criar(db: Session, venda: Venda):
        db.add(venda)
        db.flush()          # gera o ID antes do commit
        return venda

    @staticmethod
    def salvar(db: Session):
        db.commit()

    @staticmethod
    def atualizar(db: Session):
        db.commit()

    @staticmethod
    def excluir(db: Session, venda: Venda):
        db.delete(venda)
        db.commit()