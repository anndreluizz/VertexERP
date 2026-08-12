import os

from sqlalchemy.orm import Session

from app.repositories.configuracao_repository import (
    ConfiguracaoRepository,
)

DIRETORIO_UPLOADS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "uploads",
)


class ConfiguracaoService:

    @staticmethod
    def buscar(db: Session):
        return ConfiguracaoRepository.buscar(db)

    @staticmethod
    def atualizar(db: Session, dados):
        config = ConfiguracaoRepository.buscar(db)

        for campo, valor in dados.dict(exclude_unset=True).items():
            setattr(config, campo, valor)

        return ConfiguracaoRepository.salvar(db, config)

    @staticmethod
    def salvar_logo(db: Session, nome_arquivo: str, conteudo: bytes):
        if not conteudo:
            raise Exception("Arquivo de logo vazio.")

        os.makedirs(DIRETORIO_UPLOADS, exist_ok=True)

        extensao = os.path.splitext(nome_arquivo)[1].lower() or ".png"

        if extensao not in (".png", ".jpg", ".jpeg"):
            raise Exception(
                "Formato de imagem não suportado. Use PNG ou JPG."
            )

        nome_salvo = f"logo{extensao}"
        caminho = os.path.join(DIRETORIO_UPLOADS, nome_salvo)

        with open(caminho, "wb") as arquivo:
            arquivo.write(conteudo)

        config = ConfiguracaoRepository.buscar(db)
        config.logo_filename = nome_salvo

        return ConfiguracaoRepository.salvar(db, config)

    @staticmethod
    def caminho_logo(db: Session) -> str | None:
        config = ConfiguracaoRepository.buscar(db)

        if not config.logo_filename:
            return None

        caminho = os.path.join(DIRETORIO_UPLOADS, config.logo_filename)

        if not os.path.isfile(caminho):
            return None

        return caminho
