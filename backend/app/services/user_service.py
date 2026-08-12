from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.models.user import User
from app.schemas.user import UserCreate
from app.repositories.user_repository import UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:

    @staticmethod
    def criar_usuario(db: Session, dados: UserCreate):

        usuario = UserRepository.buscar_por_email(db, dados.email)

        if usuario:
            raise Exception("E-mail já cadastrado.")

        senha_hash = pwd_context.hash(dados.senha)

        novo_usuario = User(
            nome=dados.nome,
            email=dados.email,
            senha=senha_hash,
            ativo=True,
            admin=False
        )

        return UserRepository.criar(db, novo_usuario)

    @staticmethod
    def listar_usuarios(db: Session, skip: int = 0, limit: int = 100):
        return UserRepository.listar(db, skip, limit)

    @staticmethod
    def definir_admin(db: Session, user_id: int, admin: bool):

        usuario = UserRepository.buscar_por_id(db, user_id)

        if not usuario:
            raise Exception("Usuário não encontrado.")

        usuario.admin = admin

        db.commit()
        db.refresh(usuario)

        return usuario

    @staticmethod
    def definir_ativo(db: Session, user_id: int, ativo: bool):

        usuario = UserRepository.buscar_por_id(db, user_id)

        if not usuario:
            raise Exception("Usuário não encontrado.")

        usuario.ativo = ativo

        db.commit()
        db.refresh(usuario)

        return usuario