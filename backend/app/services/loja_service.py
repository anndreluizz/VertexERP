from sqlalchemy.orm import Session

from app.models.loja import Loja
from app.repositories.loja_repository import LojaRepository
from app.schemas.loja import LojaCreate


class LojaService:

    @staticmethod
    def criar(db: Session, dados: LojaCreate):

        if LojaRepository.buscar_por_nome(db, dados.nome):
            raise Exception("Já existe uma loja com esse nome.")

        nova = Loja(nome=dados.nome, ativa=True)

        return LojaRepository.criar(db, nova)

    @staticmethod
    def listar(db: Session):
        return LojaRepository.listar(db)
