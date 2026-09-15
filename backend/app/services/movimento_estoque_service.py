from sqlalchemy.orm import Session

from app.models.movimento_estoque import MovimentoEstoque
from app.repositories.produto_repository import ProdutoRepository
from app.repositories.movimento_estoque_repository import (
    MovimentoEstoqueRepository,
)
from app.schemas.movimento_estoque import MovimentoEstoqueCreate


class MovimentoEstoqueService:

    @staticmethod
    def criar(
        db: Session,
        dados: MovimentoEstoqueCreate,
        usuario_id: int,
        loja_id: int | None = None,
    ):

        produto = ProdutoRepository.buscar_por_id(db, dados.produto_id)

        if not produto:
            raise Exception("Produto não encontrado.")

        tipo = dados.tipo.upper()

        if tipo == "ENTRADA":
            produto.estoque += dados.quantidade

        elif tipo == "SAIDA":
            if dados.quantidade > produto.estoque:
                raise Exception("Estoque insuficiente para essa saída.")
            produto.estoque -= dados.quantidade

        elif tipo == "AJUSTE":
            produto.estoque = dados.quantidade

        else:
            raise Exception("Tipo de movimento inválido.")

        movimento = MovimentoEstoque(
            produto_id=produto.id,
            usuario_id=usuario_id,
            loja_id=loja_id,
            tipo=tipo,
            quantidade=dados.quantidade,
            motivo=dados.motivo,
        )

        ProdutoRepository.atualizar(db, produto)

        return MovimentoEstoqueRepository.criar(db, movimento)

    @staticmethod
    def listar(db: Session):
        return MovimentoEstoqueRepository.listar(db)

    @staticmethod
    def listar_por_produto(db: Session, produto_id: int):
        return MovimentoEstoqueRepository.listar_por_produto(
            db,
            produto_id,
        )
