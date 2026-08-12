from sqlalchemy.orm import Session

from app.models.device_token import DeviceToken


class DeviceTokenRepository:

    @staticmethod
    def buscar_por_token(db: Session, token: str):
        return (
            db.query(DeviceToken)
            .filter(DeviceToken.token == token)
            .first()
        )

    @staticmethod
    def criar(db: Session, device_token: DeviceToken):
        db.add(device_token)
        db.commit()
        db.refresh(device_token)
        return device_token

    @staticmethod
    def atualizar(db: Session, device_token: DeviceToken):
        db.commit()
        db.refresh(device_token)
        return device_token

    @staticmethod
    def remover(db: Session, device_token: DeviceToken):
        db.delete(device_token)
        db.commit()

    @staticmethod
    def tokens_de_usuarios(
        db: Session, usuario_ids: list[int]
    ) -> list[str]:

        if not usuario_ids:
            return []

        registros = (
            db.query(DeviceToken)
            .filter(DeviceToken.usuario_id.in_(usuario_ids))
            .all()
        )

        return [registro.token for registro in registros]
