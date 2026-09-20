from sqlalchemy.orm import Session

from app.models.centro_custo import CentroCusto
from app.schemas.centro_custo import (
    CentroCustoCreate,
    CentroCustoUpdate,
)
from app.repositories.centro_custo_repository import (
    CentroCustoRepository,
)


class CentroCustoService:

    @staticmethod
    def criar(db: Session, dados: CentroCustoCreate):

        existente = CentroCustoRepository.buscar_por_nome(
            db, dados.nome
        )

        if existente:
            raise Exception("Centro de custo já cadastrado.")

        centro = CentroCusto(nome=dados.nome)

        return CentroCustoRepository.criar(db, centro)

    @staticmethod
    def listar(db: Session):
        return CentroCustoRepository.listar(db)

    @staticmethod
    def atualizar(
        db: Session,
        centro_id: int,
        dados: CentroCustoUpdate,
    ):

        centro = CentroCustoRepository.buscar_por_id(
            db, centro_id
        )

        if not centro:
            raise Exception("Centro de custo não encontrado.")

        duplicado = CentroCustoRepository.buscar_por_nome(
            db, dados.nome
        )

        if duplicado and duplicado.id != centro_id:
            raise Exception("Já existe um centro de custo com esse nome.")

        centro.nome = dados.nome

        return CentroCustoRepository.atualizar(db, centro)

    @staticmethod
    def excluir(db: Session, centro_id: int):

        centro = CentroCustoRepository.buscar_por_id(
            db, centro_id
        )

        if not centro:
            raise Exception("Centro de custo não encontrado.")

        CentroCustoRepository.excluir(db, centro)
