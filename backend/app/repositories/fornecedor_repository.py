from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.fornecedor import Fornecedor


class FornecedorCNPJDuplicadoError(Exception):
    """Levantado quando já existe um fornecedor cadastrado com o mesmo CNPJ."""


class FornecedorRepository:

    @staticmethod
    def criar(db: Session, fornecedor: Fornecedor) -> Fornecedor:

        db.add(fornecedor)
        FornecedorRepository._commit(db)
        db.refresh(fornecedor)

        return fornecedor

    @staticmethod
    def listar(
        db: Session,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Fornecedor]:
        return (
            db.query(Fornecedor)
            .order_by(Fornecedor.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def buscar_por_id(
        db: Session,
        fornecedor_id: int,
    ) -> Optional[Fornecedor]:

        return (
            db.query(Fornecedor)
            .filter(Fornecedor.id == fornecedor_id)
            .first()
        )

    @staticmethod
    def buscar_por_cnpj(
        db: Session,
        cnpj: str,
    ) -> Optional[Fornecedor]:
        """cnpj precisa vir ja normalizado (so' digitos) -- ver
        FornecedorService, que normaliza no criar/atualizar."""

        return (
            db.query(Fornecedor)
            .filter(Fornecedor.cnpj == cnpj)
            .first()
        )

    @staticmethod
    def atualizar(db: Session) -> None:
        FornecedorRepository._commit(db)

    # ==========================================
    # INTERNO
    # ==========================================

    @staticmethod
    def _commit(db: Session) -> None:
        """
        Executa o commit tratando violação de unicidade do CNPJ.
        Mantém o repository livre de detalhes de HTTP.
        """

        try:
            db.commit()

        except IntegrityError as exc:

            db.rollback()

            if "fornecedores_cnpj_key" in str(exc.orig):
                raise FornecedorCNPJDuplicadoError() from exc

            raise
