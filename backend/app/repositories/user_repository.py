from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:

    @staticmethod
    def buscar_por_email(db: Session, email: str):
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def buscar_por_id(db: Session, user_id: int):
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return (
            db.query(User)
            .order_by(User.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def criar(db: Session, user: User):
        db.add(user)
        db.commit()
        db.refresh(user)
        return user