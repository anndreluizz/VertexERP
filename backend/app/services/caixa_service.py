from datetime import datetime

from sqlalchemy.orm import Session

from app.models.caixa import Caixa
from app.repositories.caixa_repository import CaixaRepository
from app.schemas.caixa import CaixaCreate


class CaixaService:

    @staticmethod
    def abrir(db: Session, dados: CaixaCreate):

        caixa = CaixaRepository.buscar_aberto(db)

        if caixa:
            raise Exception("Já existe um caixa aberto.")

        novo = Caixa(
            saldo_inicial=dados.saldo_inicial,
            saldo_final=dados.saldo_inicial,
            status="ABERTO"
        )

        return CaixaRepository.criar(db, novo)

    @staticmethod
    def fechar(db: Session):

        caixa = CaixaRepository.buscar_aberto(db)

        if not caixa:
            raise Exception("Nenhum caixa aberto.")

        caixa.status = "FECHADO"
        caixa.data_fechamento = datetime.utcnow()

        return CaixaRepository.atualizar(db, caixa)

    @staticmethod
    def caixa_aberto(db: Session):
        return CaixaRepository.buscar_aberto(db)