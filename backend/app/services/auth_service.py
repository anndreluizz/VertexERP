import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken
from app.repositories.refresh_token_repository import RefreshTokenRepository

DIAS_VALIDADE_REFRESH = 90


class AuthService:

    @staticmethod
    def gerar_refresh_token(
        db: Session,
        usuario_id: int,
        dispositivo: str | None = None,
    ) -> str:

        token = secrets.token_urlsafe(48)

        novo = RefreshToken(
            usuario_id=usuario_id,
            token=token,
            dispositivo=dispositivo,
            expira_em=datetime.utcnow()
            + timedelta(days=DIAS_VALIDADE_REFRESH),
        )

        RefreshTokenRepository.criar(db, novo)

        return token

    @staticmethod
    def validar_refresh_token(db: Session, token: str) -> RefreshToken | None:

        sessao = RefreshTokenRepository.buscar_por_token(db, token)

        if not sessao:
            return None

        if sessao.revogado:
            return None

        if sessao.expira_em < datetime.utcnow():
            return None

        sessao.ultimo_uso_em = datetime.now()
        RefreshTokenRepository.atualizar(db, sessao)

        return sessao

    @staticmethod
    def listar_sessoes(db: Session, usuario_id: int):
        return RefreshTokenRepository.listar_ativos_do_usuario(
            db, usuario_id
        )

    @staticmethod
    def revogar_sessao(db: Session, usuario_id: int, sessao_id: int):

        sessao = RefreshTokenRepository.buscar_por_id(db, sessao_id)

        # so revoga sessao do proprio usuario -- sem isso qualquer
        # pessoa logada poderia derrubar a sessao de outra so' adivinhando
        # o id
        if not sessao or sessao.usuario_id != usuario_id:
            raise Exception("Sessão não encontrada.")

        sessao.revogado = True
        RefreshTokenRepository.atualizar(db, sessao)
