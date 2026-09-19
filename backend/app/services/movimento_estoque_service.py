from sqlalchemy.orm import Session

from app.models.movimento_estoque import MovimentoEstoque
from app.repositories.estoque_loja_repository import EstoqueLojaRepository
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
        transferencia_id: int | None = None,
    ):

        produto = ProdutoRepository.buscar_por_id(db, dados.produto_id)

        if not produto:
            raise Exception("Produto não encontrado.")

        tipo = dados.tipo.upper()

        # quantidade "atual" pra validar SAIDA e calcular o delta de
        # AJUSTE e a da PROPRIA loja (nao o agregado entre lojas) --
        # senao uma saida seria bloqueada/liberada com base no estoque
        # de outra loja, ou um ajuste "pra 10" na Filial na verdade
        # setaria o total da empresa pra 10
        if loja_id is not None:
            atual = EstoqueLojaRepository.obter_ou_criar(
                db, produto.id, loja_id
            ).quantidade
        else:
            atual = produto.estoque

        if tipo == "ENTRADA":
            delta = dados.quantidade

        elif tipo == "SAIDA":
            if dados.quantidade > atual:
                raise Exception("Estoque insuficiente para essa saída.")
            delta = -dados.quantidade

        elif tipo == "AJUSTE":
            delta = dados.quantidade - atual

        else:
            raise Exception("Tipo de movimento inválido.")

        EstoqueLojaRepository.ajustar(db, produto, loja_id, delta)

        movimento = MovimentoEstoque(
            produto_id=produto.id,
            usuario_id=usuario_id,
            loja_id=loja_id,
            tipo=tipo,
            quantidade=dados.quantidade,
            motivo=dados.motivo,
            transferencia_id=transferencia_id,
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
