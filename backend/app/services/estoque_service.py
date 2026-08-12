from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.models.movimento_estoque import MovimentoEstoque
from app.repositories.movimento_estoque_repository import (
    MovimentoEstoqueRepository,
)
from app.schemas.movimento_estoque import MovimentoEstoqueCreate


class EstoqueService:

    @staticmethod
    def ajustar(
        db: Session,
        dados: MovimentoEstoqueCreate,
        usuario_id: int,
    ):

        produto = (
            db.query(Produto)
            .filter(Produto.id == dados.produto_id)
            .first()
        )

        if produto is None:
            raise Exception("Produto não encontrado.")

        if dados.tipo.value == "ENTRADA":
            produto.estoque += dados.quantidade
        else:
            if produto.estoque < dados.quantidade:
                raise Exception(
                    f"Estoque insuficiente para ajuste de saída de {produto.nome}."
                )
            produto.estoque -= dados.quantidade

        db.add(produto)

        movimento = MovimentoEstoque(
            produto_id=produto.id,
            usuario_id=usuario_id,
            tipo=dados.tipo.value,
            quantidade=dados.quantidade,
            motivo=dados.motivo,
        )

        return MovimentoEstoqueRepository.criar(db, movimento)

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return MovimentoEstoqueRepository.listar(db, skip, limit)

    @staticmethod
    def listar_por_produto(
        db: Session,
        produto_id: int,
        skip: int = 0,
        limit: int = 100,
    ):
        return MovimentoEstoqueRepository.listar_por_produto(
            db, produto_id, skip, limit
        )
