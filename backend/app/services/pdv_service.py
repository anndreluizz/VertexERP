from sqlalchemy.orm import Session

from app.models.produto import Produto


class PDVService:

    @staticmethod
    def buscar_produto(
        db: Session,
        codigo: str,
    ):

        produto = (
            db.query(Produto)
            .filter(
                (Produto.codigo == codigo)
                | (Produto.codigo_barras == codigo)
            )
            .first()
        )

        if produto is None:
            raise Exception(
                "Produto não encontrado."
            )

        return {
            "id": produto.id,
            "codigo": produto.codigo,
            "codigo_barras": produto.codigo_barras,
            "nome": produto.nome,
            "preco": produto.preco_venda,
            "estoque": produto.estoque,
        }