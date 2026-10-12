from sqlalchemy.orm import Session

from app.models.loja import Loja
from app.repositories.loja_repository import LojaRepository
from app.models.caixa import Caixa
from app.schemas.loja import LojaCreate, LojaUpdate


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

    @staticmethod
    def atualizar(db: Session, loja_id: int, dados: LojaUpdate):
        loja = LojaRepository.buscar_por_id(db, loja_id)

        if loja is None:
            raise LookupError("Loja não encontrada.")

        if dados.nome is not None:
            nome = dados.nome.strip()

            if not nome:
                raise Exception("Informe o nome da loja.")

            outra = LojaRepository.buscar_por_nome(db, nome)

            if outra and outra.id != loja.id:
                raise Exception("Já existe uma loja com esse nome.")

            loja.nome = nome

        if dados.ativa is False and loja.ativa:
            if db.query(Caixa).filter(
                Caixa.loja_id == loja.id, Caixa.status == "ABERTO"
            ).first():
                raise Exception(
                    "Essa loja tem caixa aberto. Feche o caixa antes de "
                    "desativar."
                )

            if db.query(Loja).filter(Loja.ativa.is_(True)).count() <= 1:
                raise Exception("Precisa ficar pelo menos uma loja ativa.")

        if dados.ativa is not None:
            loja.ativa = dados.ativa

        db.commit()
        db.refresh(loja)
        return loja
