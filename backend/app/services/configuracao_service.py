import base64

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

        campos = dados.model_dump(exclude_unset=True, exclude={"logo_base64"})

        for campo, valor in campos.items():
            setattr(configuracao, campo, valor)

        # mesmo padrao do Cliente.foto_base64: so troca o logo se veio
        # um valor de verdade, senao mantem o que ja estava salvo
        if dados.logo_base64:
            configuracao.logo = base64.b64decode(dados.logo_base64)

        return ConfiguracaoRepository.atualizar(db, configuracao)
