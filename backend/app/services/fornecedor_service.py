from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.fornecedor import Fornecedor
from app.schemas.fornecedor import (
    FornecedorCreate,
    FornecedorUpdate,
)
from app.repositories.fornecedor_repository import (
    FornecedorRepository,
)


class FornecedorService:

    @staticmethod
    def criar(db: Session, dados: FornecedorCreate):

        fornecedor = Fornecedor(
            razao_social=dados.razao_social,
            nome_fantasia=dados.nome_fantasia,
            cnpj=dados.cnpj,
            email=dados.email,
            telefone=dados.telefone,
            cidade=dados.cidade,
            estado=dados.estado,
            ativo=True,
        )

        return FornecedorRepository.criar(db, fornecedor)

    @staticmethod
    def listar(db: Session):
        return FornecedorRepository.listar(db)

    @staticmethod
    def buscar(db: Session, fornecedor_id: int):

        fornecedor = FornecedorRepository.buscar_por_id(
            db,
            fornecedor_id
        )

        if not fornecedor:
            raise HTTPException(
                status_code=404,
                detail="Fornecedor não encontrado."
            )

        return fornecedor

    @staticmethod
    def atualizar(
        db: Session,
        fornecedor_id: int,
        dados: FornecedorUpdate,
    ):

        fornecedor = FornecedorRepository.buscar_por_id(
            db,
            fornecedor_id
        )

        if not fornecedor:
            raise HTTPException(
                status_code=404,
                detail="Fornecedor não encontrado."
            )

        fornecedor.razao_social = dados.razao_social
        fornecedor.nome_fantasia = dados.nome_fantasia
        fornecedor.cnpj = dados.cnpj
        fornecedor.email = dados.email
        fornecedor.telefone = dados.telefone
        fornecedor.cidade = dados.cidade
        fornecedor.estado = dados.estado
        fornecedor.ativo = dados.ativo

        FornecedorRepository.atualizar(db)

        return fornecedor

    @staticmethod
    def excluir(
        db: Session,
        fornecedor_id: int,
    ):

        fornecedor = FornecedorRepository.buscar_por_id(
            db,
            fornecedor_id
        )

        if not fornecedor:
            raise HTTPException(
                status_code=404,
                detail="Fornecedor não encontrado."
            )

        FornecedorRepository.excluir(db, fornecedor)

        return {
            "message": "Fornecedor excluído com sucesso."
        }