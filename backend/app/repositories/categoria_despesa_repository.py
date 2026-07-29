from sqlalchemy.orm import Session

from app.models.categoria_despesa import CategoriaDespesa


class CategoriaDespesaRepository:

    @staticmethod
    def criar(db: Session, categoria: CategoriaDespesa):
        db.add(categoria)
        db.commit()
        db.refresh(categoria)
        return categoria

    @staticmethod
    def listar(db: Session):
        return (
            db.query(CategoriaDespesa)
            .order_by(CategoriaDespesa.nome)
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, categoria_id: int):
        return (
            db.query(CategoriaDespesa)
            .filter(CategoriaDespesa.id == categoria_id)
            .first()
        )

    @staticmethod
    def buscar_por_nome(db: Session, nome: str):
        return (
            db.query(CategoriaDespesa)
            .filter(CategoriaDespesa.nome == nome)
            .first()
        )

    @staticmethod
    def atualizar(db: Session, categoria: CategoriaDespesa):
        db.commit()
        db.refresh(categoria)
        return categoria

    @staticmethod
    def excluir(db: Session, categoria: CategoriaDespesa):
        db.delete(categoria)
        db.commit()
