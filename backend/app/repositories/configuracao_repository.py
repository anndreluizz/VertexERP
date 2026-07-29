from sqlalchemy.orm import Session

from app.models.configuracao import Configuracao


class ConfiguracaoRepository:

    @staticmethod
    def buscar(db: Session):
        return db.query(Configuracao).first()

    @staticmethod
    def criar(db: Session, configuracao: Configuracao):
        db.add(configuracao)
        db.commit()
        db.refresh(configuracao)
        return configuracao

    @staticmethod
    def atualizar(db: Session, configuracao: Configuracao):
        db.commit()
        db.refresh(configuracao)
        return configuracao
