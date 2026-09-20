from sqlalchemy.orm import Session

from app.models.kit_item import KitItem
from app.repositories.kit_item_repository import KitItemRepository
from app.repositories.produto_repository import ProdutoRepository
from app.schemas.kit_item import KitItemCreate


class KitItemService:

    @staticmethod
    def listar(db: Session, kit_id: int):
        return KitItemRepository.listar_por_kit(db, kit_id)

    @staticmethod
    def adicionar(db: Session, kit_id: int, dados: KitItemCreate):
        kit = ProdutoRepository.buscar_por_id(db, kit_id)

        if not kit:
            raise Exception("Produto não encontrado.")

        if not kit.eh_kit:
            raise Exception(
                'Marque "Este produto é um kit" antes de adicionar '
                "componentes."
            )

        if dados.produto_componente_id == kit_id:
            raise Exception("Um kit não pode ter a si mesmo como componente.")

        componente = ProdutoRepository.buscar_por_id(
            db, dados.produto_componente_id
        )

        if not componente:
            raise Exception("Produto componente não encontrado.")

        if componente.eh_kit:
            raise Exception(
                f'"{componente.nome}" é um kit e não pode ser componente '
                "de outro kit."
            )

        if dados.quantidade <= 0:
            raise Exception("A quantidade precisa ser maior que zero.")

        item = KitItem(
            kit_id=kit_id,
            produto_componente_id=dados.produto_componente_id,
            quantidade=dados.quantidade,
        )

        return KitItemRepository.criar(db, item)

    @staticmethod
    def remover(db: Session, kit_id: int, item_id: int):
        item = KitItemRepository.buscar_por_id(db, item_id)

        if not item or item.kit_id != kit_id:
            raise Exception("Componente não encontrado nesse kit.")

        KitItemRepository.remover(db, item)
