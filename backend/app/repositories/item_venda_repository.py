from sqlalchemy.orm import Session

from app.models.item_venda import ItemVenda


class ItemVendaRepository:

    @staticmethod
    def criar(db: Session, item: ItemVenda):
        db.add(item)