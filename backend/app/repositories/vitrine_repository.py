from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.item_venda import ItemVenda
from app.models.produto import Produto
from app.models.produto_foto import ProdutoFoto
from app.models.venda import Venda


class VitrineRepository:

    @staticmethod
    def listar_publicados(db: Session) -> list[Produto]:
        return (
            db.query(Produto)
            .options(selectinload(Produto.fotos), selectinload(Produto.marca))
            .filter(Produto.ativo.is_(True), Produto.vitrine_publicar.is_(True))
            .order_by(Produto.nome, Produto.id)
            .all()
        )

    @staticmethod
    def mais_vendidos(
        db: Session, produto_ids: list[int], desde: datetime, limite: int
    ) -> list[int]:
        if not produto_ids:
            return []
        total = func.sum(ItemVenda.quantidade)
        linhas = (
            db.query(ItemVenda.produto_id)
            .join(Venda, Venda.id == ItemVenda.venda_id)
            .filter(
                ItemVenda.produto_id.in_(produto_ids),
                Venda.status != "CANCELADA",
                Venda.data >= desde,
            )
            .group_by(ItemVenda.produto_id)
            .order_by(total.desc(), ItemVenda.produto_id)
            .limit(limite)
            .all()
        )
        return [linha[0] for linha in linhas]

    @staticmethod
    def buscar_foto_publicada(db: Session, foto_id: int) -> ProdutoFoto | None:
        return (
            db.query(ProdutoFoto)
            .join(Produto, Produto.id == ProdutoFoto.produto_id)
            .filter(
                ProdutoFoto.id == foto_id,
                Produto.ativo.is_(True),
                Produto.vitrine_publicar.is_(True),
            )
            .first()
        )
