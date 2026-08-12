from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.repositories.produto_repository import ProdutoRepository
from app.schemas.produto import ProdutoCreate, ProdutoUpdate


class ProdutoService:

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return ProdutoRepository.listar(db, skip, limit)

    @staticmethod
    def buscar(db: Session, produto_id: int):
        return ProdutoRepository.buscar_por_id(db, produto_id)

    @staticmethod
    def criar(db: Session, dados: ProdutoCreate):
        produto = Produto(**dados.dict())
        return ProdutoRepository.criar(db, produto)

    @staticmethod
    def atualizar(db: Session, produto_id: int, dados: ProdutoUpdate):
        produto = ProdutoRepository.buscar_por_id(db, produto_id)

        if not produto:
            return None

        for campo, valor in dados.dict().items():
            setattr(produto, campo, valor)

        return ProdutoRepository.atualizar(db, produto)

    @staticmethod
    def excluir(db: Session, produto_id: int):
        produto = ProdutoRepository.buscar_por_id(db, produto_id)

        if not produto:
            return False

        ProdutoRepository.excluir(db, produto)
        return True