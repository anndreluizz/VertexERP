from sqlalchemy.orm import Session

from app.models.produto_foto import ProdutoFoto


class ProdutoFotoRepository:

    @staticmethod
    def criar(db: Session, foto: ProdutoFoto):
        db.add(foto)
        db.commit()
        db.refresh(foto)
        return foto

    @staticmethod
    def listar_por_produto(db: Session, produto_id: int):
        return (
            db.query(ProdutoFoto)
            .filter(ProdutoFoto.produto_id == produto_id)
            .order_by(ProdutoFoto.ordem)
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, foto_id: int):
        return (
            db.query(ProdutoFoto)
            .filter(ProdutoFoto.id == foto_id)
            .first()
        )

    @staticmethod
    def maior_ordem(db: Session, produto_id: int) -> int:
        maior = (
            db.query(ProdutoFoto.ordem)
            .filter(ProdutoFoto.produto_id == produto_id)
            .order_by(ProdutoFoto.ordem.desc())
            .first()
        )
        return maior[0] if maior else -1

    @staticmethod
    def desmarcar_principal_do_produto(db: Session, produto_id: int):
        (
            db.query(ProdutoFoto)
            .filter(
                ProdutoFoto.produto_id == produto_id,
                ProdutoFoto.principal.is_(True),
            )
            .update({ProdutoFoto.principal: False})
        )
        db.commit()

    @staticmethod
    def atualizar(db: Session, foto: ProdutoFoto):
        db.commit()
        db.refresh(foto)
        return foto

    @staticmethod
    def excluir(db: Session, foto: ProdutoFoto):
        db.delete(foto)
        db.commit()
