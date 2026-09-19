from sqlalchemy.orm import Session

from app.models.item_compra import ItemCompra


class ItemCompraRepository:

    @staticmethod
    def criar(
        db: Session,
        item: ItemCompra,
    ):
        db.add(item)
        db.flush()
        return item
