from sqlalchemy.orm import Session

from app.models.item_venda import ItemVenda


class ItemVendaRepository:

    @staticmethod
    def criar(db: Session, item: ItemVenda):
        db.add(item)

    @staticmethod
    def listar_por_venda(db: Session, venda_id: int):
        return (
            db.query(ItemVenda)
            .filter(ItemVenda.venda_id == venda_id)
            .all()
        )