import base64

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.repositories.produto_repository import ProdutoRepository
from app.schemas.produto import ProdutoCreate, ProdutoUpdate


class ProdutoService:

    @staticmethod
    def listar(db: Session):
        return ProdutoRepository.listar(db)

    @staticmethod
    def buscar(db: Session, produto_id: int):
        return ProdutoRepository.buscar_por_id(db, produto_id)

    @staticmethod
    def criar(db: Session, dados: ProdutoCreate):

        condicoes = [Produto.codigo == dados.codigo]

        if dados.codigo_barras:
            condicoes.append(Produto.codigo_barras == dados.codigo_barras)

        existente = (
            db.query(Produto)
            .filter(or_(*condicoes))
            .first()
        )

        if existente:
            if existente.codigo == dados.codigo:
                raise ValueError(
                    f'Já existe um produto com o código '
                    f'"{dados.codigo}".'
                )
            raise ValueError(
                f'Já existe um produto ("{existente.nome}") '
                f'cadastrado com esse código de barras.'
            )

        campos = dados.dict(exclude={"foto_base64"})
        produto = Produto(**campos)

        if dados.foto_base64:
            produto.foto = base64.b64decode(dados.foto_base64)

        return ProdutoRepository.criar(db, produto)

    @staticmethod
    def atualizar(db: Session, produto_id: int, dados: ProdutoUpdate):
        produto = ProdutoRepository.buscar_por_id(db, produto_id)

        if not produto:
            return None

        campos = dados.dict(exclude={"foto_base64"})

        for campo, valor in campos.items():
            setattr(produto, campo, valor)

        if dados.foto_base64:
            produto.foto = base64.b64decode(dados.foto_base64)

        return ProdutoRepository.atualizar(db, produto)

    @staticmethod
    def excluir(db: Session, produto_id: int):
        produto = ProdutoRepository.buscar_por_id(db, produto_id)

        if not produto:
            return False

        ProdutoRepository.excluir(db, produto)
        return True