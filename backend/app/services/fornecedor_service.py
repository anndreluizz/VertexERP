from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.fornecedor import Fornecedor
from app.schemas.fornecedor import (
    FornecedorCreate,
    FornecedorUpdate,
)
from app.repositories.fornecedor_repository import (
    FornecedorRepository,
    FornecedorCNPJDuplicadoError,
)


class FornecedorService:

    @staticmethod
    def criar(db: Session, dados: FornecedorCreate) -> Fornecedor:

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

        try:
            return FornecedorRepository.criar(db, fornecedor)

        except FornecedorCNPJDuplicadoError:
            raise HTTPException(
                status_code=409,
                detail="Já existe um fornecedor cadastrado com este CNPJ.",
            )

    @staticmethod
    def listar(
        db: Session, skip: int = 0, limit: int = 100
    ) -> list[Fornecedor]:
        return FornecedorRepository.listar(db, skip, limit)

    @staticmethod
    def buscar(db: Session, fornecedor_id: int) -> Fornecedor:

        fornecedor = FornecedorRepository.buscar_por_id(
            db,
            fornecedor_id,
        )

        if not fornecedor:
            raise HTTPException(
                status_code=404,
                detail="Fornecedor não encontrado.",
            )

        return fornecedor

    @staticmethod
    def atualizar(
        db: Session,
        fornecedor_id: int,
        dados: FornecedorUpdate,
    ) -> Fornecedor:

        # Reaproveita buscar() -> já trata o 404
        fornecedor = FornecedorService.buscar(db, fornecedor_id)

        fornecedor.razao_social = dados.razao_social
        fornecedor.nome_fantasia = dados.nome_fantasia
        fornecedor.cnpj = dados.cnpj
        fornecedor.email = dados.email
        fornecedor.telefone = dados.telefone
        fornecedor.cidade = dados.cidade
        fornecedor.estado = dados.estado
        fornecedor.ativo = dados.ativo

        try:
            FornecedorRepository.atualizar(db)

        except FornecedorCNPJDuplicadoError:
            raise HTTPException(
                status_code=409,
                detail="Já existe um fornecedor cadastrado com este CNPJ.",
            )

        return fornecedor

    @staticmethod
    def excluir(db: Session, fornecedor_id: int) -> dict:

        # Reaproveita buscar() -> já trata o 404
        fornecedor = FornecedorService.buscar(db, fornecedor_id)

        FornecedorRepository.excluir(db, fornecedor)

        return {
            "message": "Fornecedor excluído com sucesso."
        }