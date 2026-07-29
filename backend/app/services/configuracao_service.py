from sqlalchemy.orm import Session

from app.models.configuracao import Configuracao
from app.repositories.configuracao_repository import ConfiguracaoRepository
from app.schemas.configuracao import ConfiguracaoUpdate


class ConfiguracaoService:

    @staticmethod
    def buscar(db: Session):

        configuracao = ConfiguracaoRepository.buscar(db)

        if not configuracao:
            configuracao = ConfiguracaoRepository.criar(
                db,
                Configuracao()
            )

        return configuracao

    @staticmethod
    def atualizar(db: Session, dados: ConfiguracaoUpdate):

        configuracao = ConfiguracaoService.buscar(db)

        for campo, valor in dados.dict(exclude_unset=True).items():
            setattr(configuracao, campo, valor)

        return ConfiguracaoRepository.atualizar(db, configuracao)
