from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.schemas.categoria import CategoriaCreate, CategoriaUpdate
from app.repositories.categoria_repository import CategoriaRepository


class CategoriaService:

    @staticmethod
    def criar(db: Session, dados: CategoriaCreate):

        categoria = CategoriaRepository.buscar_por_nome(
            db,
            dados.nome
        )

        if categoria:
            raise Exception("Categoria já cadastrada.")

        nova_categoria = Categoria(
            nome=dados.nome,
            descricao=dados.descricao,
            ativo=True
        )

        return CategoriaRepository.criar(db, nova_categoria)

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return CategoriaRepository.listar(db, skip, limit)

    @staticmethod
    def buscar_por_id(db: Session, categoria_id: int):
        return CategoriaRepository.buscar_por_id(db, categoria_id)

    @staticmethod
    def atualizar(
        db: Session,
        categoria_id: int,
        dados: CategoriaUpdate
    ):

        categoria = CategoriaRepository.buscar_por_id(
            db,
            categoria_id
        )

        if not categoria:
            raise Exception("Categoria não encontrada.")

        for campo, valor in dados.dict(exclude_unset=True).items():
            setattr(categoria, campo, valor)

        return CategoriaRepository.atualizar(db, categoria)

    @staticmethod
    def excluir(db: Session, categoria_id: int):

        categoria = CategoriaRepository.buscar_por_id(
            db,
            categoria_id
        )

        if not categoria:
            raise Exception("Categoria não encontrada.")

        CategoriaRepository.excluir(db, categoria)

        return {
            "mensagem": "Categoria excluída com sucesso."
        }