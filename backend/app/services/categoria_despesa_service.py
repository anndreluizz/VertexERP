from sqlalchemy.orm import Session

from app.models.categoria_despesa import CategoriaDespesa
from app.schemas.categoria_despesa import (
    CategoriaDespesaCreate,
    CategoriaDespesaUpdate,
)
from app.repositories.categoria_despesa_repository import (
    CategoriaDespesaRepository,
)


class CategoriaDespesaService:

    @staticmethod
    def criar(db: Session, dados: CategoriaDespesaCreate):

        existente = CategoriaDespesaRepository.buscar_por_nome(
            db, dados.nome
        )

        if existente:
            raise Exception("Categoria já cadastrada.")

        categoria = CategoriaDespesa(nome=dados.nome)

        return CategoriaDespesaRepository.criar(db, categoria)

    @staticmethod
    def listar(db: Session):
        return CategoriaDespesaRepository.listar(db)

    @staticmethod
    def atualizar(
        db: Session,
        categoria_id: int,
        dados: CategoriaDespesaUpdate,
    ):

        categoria = CategoriaDespesaRepository.buscar_por_id(
            db, categoria_id
        )

        if not categoria:
            raise Exception("Categoria não encontrada.")

        duplicada = CategoriaDespesaRepository.buscar_por_nome(
            db, dados.nome
        )

        if duplicada and duplicada.id != categoria_id:
            raise Exception("Já existe uma categoria com esse nome.")

        categoria.nome = dados.nome

        return CategoriaDespesaRepository.atualizar(db, categoria)

    @staticmethod
    def excluir(db: Session, categoria_id: int):

        categoria = CategoriaDespesaRepository.buscar_por_id(
            db, categoria_id
        )

        if not categoria:
            raise Exception("Categoria não encontrada.")

        CategoriaDespesaRepository.excluir(db, categoria)
