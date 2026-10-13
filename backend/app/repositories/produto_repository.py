from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.produto import Produto


class ProdutoRepository:

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100, loja_id: int | None = None):
        query = db.query(Produto)

        # so' entram produtos globais (loja_id NULL) e os exclusivos
        # DESSA loja -- produto exclusivo de outra loja nunca aparece
        # (ver Produto.loja_id)
        if loja_id is not None:
            query = query.filter(
                or_(Produto.loja_id.is_(None), Produto.loja_id == loja_id)
            )

        return (
            query
            .order_by(Produto.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def listar_variacoes(db: Session, produto_pai_id: int):
        return (
            db.query(Produto)
            .filter(Produto.produto_pai_id == produto_pai_id)
            .order_by(Produto.id)
            .all()
        )

    @staticmethod
    def proximo_codigo_interno(db: Session) -> int:
        """Proximo numero da sequencia de codigos internos (0001, 0002...)
        pra produto sem codigo de barras. EAN tem 8+ digitos, entao so'
        codigo numerico curto entra na conta."""
        codigos = db.query(Produto.codigo).filter(
            func.length(Produto.codigo) <= 6
        )
        numeros = [int(c) for (c,) in codigos if c.isdigit()]
        return max(numeros, default=0) + 1

    @staticmethod
    def buscar_por_id(db: Session, produto_id: int):
        return db.query(Produto).filter(
            Produto.id == produto_id
        ).first()

    @staticmethod
    def buscar_por_codigo(
        db: Session, codigo: str, loja_id: int | None = None
    ):
        """Mesmo escopo de listar(): produto global (loja_id NULL) ou
        exclusivo DESSA loja -- usado pra casar o cProd de uma NF-e com
        um produto ja cadastrado (ver ImportacaoNfeService)."""

        query = db.query(Produto).filter(Produto.codigo == codigo)

        if loja_id is not None:
            query = query.filter(
                or_(Produto.loja_id.is_(None), Produto.loja_id == loja_id)
            )
        else:
            query = query.filter(Produto.loja_id.is_(None))

        return query.first()

    @staticmethod
    def buscar_por_codigo_barras(
        db: Session, codigo_barras: str, loja_id: int | None = None
    ):
        query = db.query(Produto).filter(
            Produto.codigo_barras == codigo_barras
        )

        if loja_id is not None:
            query = query.filter(
                or_(Produto.loja_id.is_(None), Produto.loja_id == loja_id)
            )
        else:
            query = query.filter(Produto.loja_id.is_(None))

        return query.first()

    @staticmethod
    def criar(db: Session, produto: Produto):
        db.add(produto)
        db.commit()
        db.refresh(produto)
        return produto

    @staticmethod
    def atualizar(db: Session, produto: Produto):
        db.commit()
        db.refresh(produto)
        return produto

    @staticmethod
    def excluir(db: Session, produto: Produto):
        db.delete(produto)
        db.commit()