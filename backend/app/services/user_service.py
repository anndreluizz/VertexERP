from sqlalchemy.orm import Session

from app.auth.hash import gerar_hash
from app.models.user import User
from app.schemas.user import UserCreate
from app.repositories.user_repository import UserRepository


class UserService:

    @staticmethod
    def criar_usuario(db: Session, dados: UserCreate):

        usuario = UserRepository.buscar_por_email(db, dados.email)

        if usuario:
            raise Exception("E-mail já cadastrado.")

        # o primeiro usuario do sistema (dono da loja) ja nasce admin;
        # os demais (cadastrados depois, por um admin) nascem comuns
        eh_primeiro_usuario = len(UserRepository.listar(db)) == 0

        senha_hash = gerar_hash(dados.senha)

        novo_usuario = User(
            nome=dados.nome,
            email=dados.email,
            senha=senha_hash,
            ativo=True,
            admin=eh_primeiro_usuario,
        )

        return UserRepository.criar(db, novo_usuario)

    @staticmethod
    def listar_usuarios(db: Session):
        return UserRepository.listar(db)

    @staticmethod
    def existe_usuario(db: Session) -> bool:
        return len(UserRepository.listar(db)) > 0

    @staticmethod
    def atualizar(db: Session, user_id: int, dados, usuario_atual):

        usuario = UserRepository.buscar_por_id(db, user_id)

        if not usuario:
            raise Exception("Usuário não encontrado.")

        if usuario.id == usuario_atual.id and dados.ativo is False:
            raise Exception(
                "Você não pode desativar a própria conta."
            )

        for campo, valor in dados.dict(exclude_unset=True).items():
            setattr(usuario, campo, valor)

        return UserRepository.atualizar(db, usuario)