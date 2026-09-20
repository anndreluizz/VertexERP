from sqlalchemy.orm import Session

from app.models.perfil import Perfil


class PerfilRepository:

    @staticmethod
    def criar(db: Session, perfil: Perfil):
        db.add(perfil)
        db.commit()
        db.refresh(perfil)
        return perfil

    @staticmethod
    def listar(db: Session):
        return db.query(Perfil).order_by(Perfil.nome).all()

    @staticmethod
    def buscar_por_id(db: Session, perfil_id: int):
        return db.query(Perfil).filter(Perfil.id == perfil_id).first()

    @staticmethod
    def buscar_por_nome(db: Session, nome: str):
        return db.query(Perfil).filter(Perfil.nome == nome).first()

    @staticmethod
    def atualizar(db: Session, perfil: Perfil):
        db.commit()
        db.refresh(perfil)
        return perfil

    @staticmethod
    def excluir(db: Session, perfil: Perfil):
        db.delete(perfil)
        db.commit()
