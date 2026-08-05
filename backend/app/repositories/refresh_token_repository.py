from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:

    @staticmethod
    def criar(db: Session, refresh_token: RefreshToken):
        db.add(refresh_token)
        db.commit()
        db.refresh(refresh_token)
        return refresh_token

    @staticmethod
    def buscar_por_token(db: Session, token: str):
        return (
            db.query(RefreshToken)
            .filter(RefreshToken.token == token)
            .first()
        )

    @staticmethod
    def buscar_por_id(db: Session, refresh_token_id: int):
        return (
            db.query(RefreshToken)
            .filter(RefreshToken.id == refresh_token_id)
            .first()
        )

    @staticmethod
    def listar_ativos_do_usuario(db: Session, usuario_id: int):
        return (
            db.query(RefreshToken)
            .filter(
                RefreshToken.usuario_id == usuario_id,
                RefreshToken.revogado.is_(False),
            )
            .order_by(RefreshToken.ultimo_uso_em.desc())
            .all()
        )

    @staticmethod
    def atualizar(db: Session, refresh_token: RefreshToken):
        db.commit()
        db.refresh(refresh_token)
        return refresh_token
