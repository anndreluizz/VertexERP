from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.repositories.estoque_loja_repository import EstoqueLojaRepository


def _para_dict(produto: Produto, estoque: int):
    return {
        "id": produto.id,
        "codigo": produto.codigo,
        "codigo_barras": produto.codigo_barras,
        "nome": produto.nome,
        "preco": produto.preco_venda,
        "estoque": estoque,
        "tem_foto": produto.tem_foto,
        "favorito": produto.favorito,
    }


class PDVService:

    @staticmethod
    def buscar_produto(
        db: Session,
        codigo: str,
        loja_id: int | None = None,
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

        estoque = produto.estoque
        if loja_id is not None:
            estoque = EstoqueLojaRepository.quantidades_por_loja(
                db, [produto.id], loja_id
            ).get(produto.id, 0)

        return _para_dict(produto, estoque)

    @staticmethod
    def pesquisar(
        db: Session,
        termo: str,
        loja_id: int | None = None,
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

        mapa = {}
        if loja_id is not None:
            mapa = EstoqueLojaRepository.quantidades_por_loja(
                db, [p.id for p in produtos], loja_id
            )

        return [
            _para_dict(p, mapa.get(p.id, 0) if loja_id is not None else p.estoque)
            for p in produtos
        ]