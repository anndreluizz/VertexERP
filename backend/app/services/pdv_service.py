from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.produto import Produto


def _para_dict(produto: Produto):
    return {
        "id": produto.id,
        "codigo": produto.codigo,
        "codigo_barras": produto.codigo_barras,
        "nome": produto.nome,
        "preco": produto.preco_venda,
        "estoque": produto.estoque,
    }


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

        return _para_dict(produto)

    @staticmethod
    def pesquisar(
        db: Session,
        termo: str,
        limite: int = 20,
    ):

        padrao = f"%{termo}%"

        produtos = (
            db.query(Produto)
            .filter(
                Produto.ativo.is_(True),
                or_(
                    Produto.nome.ilike(padrao),
                    Produto.codigo.ilike(padrao),
                    Produto.codigo_barras.ilike(padrao),
                ),
            )
            .order_by(Produto.nome)
            .limit(limite)
            .all()
        )

        return [_para_dict(p) for p in produtos]