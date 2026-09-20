from sqlalchemy.orm import Session

from app.models.kit_item import KitItem


class KitItemRepository:

    @staticmethod
    def criar(db: Session, item: KitItem):
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def listar_por_kit(db: Session, kit_id: int):
        return (
            db.query(KitItem)
            .filter(KitItem.kit_id == kit_id)
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, item_id: int):
        return db.query(KitItem).filter(KitItem.id == item_id).first()

    @staticmethod
    def remover(db: Session, item: KitItem):
        db.delete(item)
        db.commit()
