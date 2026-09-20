from sqlalchemy.orm import Session, joinedload

from app.models.contagem_estoque import ContagemEstoque


class ContagemEstoqueRepository:

    @staticmethod
    def criar(db: Session, contagem: ContagemEstoque):
        db.add(contagem)
        db.commit()
        db.refresh(contagem)
        return contagem

    @staticmethod
    def buscar_por_id(db: Session, contagem_id: int):
        return (
            db.query(ContagemEstoque)
            .options(joinedload(ContagemEstoque.itens))
            .filter(ContagemEstoque.id == contagem_id)
            .first()
        )

    @staticmethod
    def buscar_aberta(db: Session, loja_id: int):
        return (
            db.query(ContagemEstoque)
            .filter(
                ContagemEstoque.loja_id == loja_id,
                ContagemEstoque.status == "ABERTA",
            )
            .first()
        )

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return (
            db.query(ContagemEstoque)
            .order_by(ContagemEstoque.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def atualizar(db: Session, contagem: ContagemEstoque):
        db.commit()
        db.refresh(contagem)
        return contagem
