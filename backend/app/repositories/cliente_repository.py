from sqlalchemy.orm import Session

from ..models.cliente import Cliente


class ClienteRepository:

    @staticmethod
    def criar(db: Session, cliente: Cliente):
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        return cliente

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100, loja_id: int | None = None):
        query = db.query(Cliente)

        if loja_id is not None:
            query = query.filter(Cliente.loja_id == loja_id)

        return (
            query
            .order_by(Cliente.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

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
    def excluir(db, cliente):
        cliente.ativo = False
        db.commit()