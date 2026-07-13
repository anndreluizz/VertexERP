from sqlalchemy.orm import Session

from app.models.cliente import Cliente


class ClienteRepository:

    @staticmethod
    def criar(db: Session, cliente: Cliente):
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        return cliente

    @staticmethod
    def listar(db: Session):
        return db.query(Cliente).all()

    @staticmethod
    def buscar_por_id(db: Session, cliente_id: int):
        return db.query(Cliente).filter(
            Cliente.id == cliente_id
        ).first()

    @staticmethod
    def buscar_por_documento(db: Session, documento: str):
        return db.query(Cliente).filter(
            Cliente.cpf_cnpj == documento
        ).first()

    @staticmethod
    def atualizar(db: Session, cliente: Cliente):
        db.commit()
        db.refresh(cliente)
        return cliente

    @staticmethod
    def excluir(db: Session, cliente: Cliente):
        db.delete(cliente)
        db.commit()