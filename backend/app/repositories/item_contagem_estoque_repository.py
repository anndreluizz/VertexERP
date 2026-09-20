from sqlalchemy.orm import Session

from app.models.item_contagem_estoque import ItemContagemEstoque


class ItemContagemEstoqueRepository:

    @staticmethod
    def buscar_por_id(db: Session, item_id: int):
        return (
            db.query(ItemContagemEstoque)
            .filter(ItemContagemEstoque.id == item_id)
            .first()
        )

    @staticmethod
    def atualizar(db: Session, item: ItemContagemEstoque):
        db.commit()
        db.refresh(item)
        return item
