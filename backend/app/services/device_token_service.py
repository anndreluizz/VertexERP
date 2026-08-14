from sqlalchemy.orm import Session

from app.models.device_token import DeviceToken
from app.repositories.device_token_repository import DeviceTokenRepository
from app.schemas.device_token import DeviceTokenCreate


class DeviceTokenService:

    @staticmethod
    def registrar(
        db: Session,
        dados: DeviceTokenCreate,
        usuario_id: int,
    ):
        # o mesmo token de aparelho pode voltar a se registrar (app
        # reaberto, reinstalado) — atualiza o dono em vez de duplicar,
        # inclusive cobrindo o caso de outro usuario logar no mesmo
        # aparelho depois
        existente = DeviceTokenRepository.buscar_por_token(
            db, dados.token
        )

        if existente:
            existente.usuario_id = usuario_id
            existente.plataforma = dados.plataforma
            return DeviceTokenRepository.atualizar(db, existente)

        novo = DeviceToken(
            usuario_id=usuario_id,
            token=dados.token,
            plataforma=dados.plataforma,
        )

        return DeviceTokenRepository.criar(db, novo)

    @staticmethod
    def remover(db: Session, token: str, usuario_id: int):

        existente = DeviceTokenRepository.buscar_por_token(db, token)

        # so remove o proprio token -- sem essa checagem, qualquer
        # usuario autenticado que descobrisse o token de outro (ex.:
        # log vazado) conseguiria apagar o cadastro de push dele
        if existente and existente.usuario_id == usuario_id:
            DeviceTokenRepository.remover(db, existente)
