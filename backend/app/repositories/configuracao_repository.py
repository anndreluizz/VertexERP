from sqlalchemy.orm import Session

from app.models.configuracao import Configuracao


class ConfiguracaoRepository:

    @staticmethod
    def buscar(db: Session) -> Configuracao:
        """Sempre existe uma única linha (id=1) — cria com valores em
        branco na primeira chamada se ainda não existir."""

        config = db.query(Configuracao).filter(Configuracao.id == 1).first()

        if config is None:
            config = Configuracao(id=1)
            db.add(config)
            db.commit()
            db.refresh(config)

        return config

    @staticmethod
    def salvar(db: Session, config: Configuracao) -> Configuracao:
        db.add(config)
        db.commit()
        db.refresh(config)
        return config
