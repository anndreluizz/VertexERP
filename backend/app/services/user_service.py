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
    def listar_usuarios(db: Session):
        return UserRepository.listar(db)