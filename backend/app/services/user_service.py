from sqlalchemy.orm import Session

from app.auth.hash import gerar_hash, verificar_hash
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

        campos = dados.dict(exclude_unset=True)

        # Se essa troca tira o admin (por remocao explicita da
        # administracao ou por desativar a conta) de quem hoje e' um
        # admin ativo, confere que sobra pelo menos mais um -- senao
        # ninguem mais consegue fazer nada que exige admin (aprovar
        # solicitacao, cadastrar usuario, cancelar venda, redefinir
        # senha de outro etc.), incluindo reverter essa mesma mudanca.
        perde_admin = usuario.admin and usuario.ativo and (
            campos.get("admin") is False or campos.get("ativo") is False
        )

        if perde_admin:
            outros_admins = (
                db.query(User)
                .filter(
                    User.admin.is_(True),
                    User.ativo.is_(True),
                    User.id != usuario.id,
                )
                .count()
            )

            if outros_admins == 0:
                raise Exception(
                    "Não é possível remover o único administrador "
                    "do sistema."
                )

        for campo, valor in campos.items():
            setattr(usuario, campo, valor)

        return UserRepository.atualizar(db, usuario)

    @staticmethod
    def trocar_senha(
        db: Session,
        usuario: User,
        senha_atual: str,
        senha_nova: str,
    ):
        """Usuário trocando a própria senha -- exige confirmar a senha
        atual antes, pra alguém que pegou uma sessão já aberta (token
        ainda válido) não conseguir travar o dono de fora só trocando
        a senha sem saber a antiga."""

        if not verificar_hash(senha_atual, usuario.senha):
            raise Exception("Senha atual incorreta.")

        if not senha_nova:
            raise Exception("Informe a nova senha.")

        usuario.senha = gerar_hash(senha_nova)

        return UserRepository.atualizar(db, usuario)

    @staticmethod
    def redefinir_senha(db: Session, user_id: int, senha_nova: str):
        """Admin redefinindo a senha de outro usuário (esqueceu a
        senha) -- não exige a senha atual, só o admin autenticado
        (ver get_current_admin na rota)."""

        usuario = UserRepository.buscar_por_id(db, user_id)

        if not usuario:
            raise Exception("Usuário não encontrado.")

        if not senha_nova:
            raise Exception("Informe a nova senha.")

        usuario.senha = gerar_hash(senha_nova)

        return UserRepository.atualizar(db, usuario)