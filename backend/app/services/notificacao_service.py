import os
import threading

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.device_token_repository import DeviceTokenRepository

_lock = threading.Lock()
_inicializado = False
_disponivel = False


def _garantir_inicializado() -> bool:
    """So inicializa o Firebase Admin na primeira notificacao de
    verdade (nao no import do modulo) — assim uma instalacao sem
    FIREBASE_CREDENTIALS_PATH configurado nunca tenta nem falha por
    causa disso, so fica sem enviar push."""

    global _inicializado, _disponivel

    if _inicializado:
        return _disponivel

    with _lock:

        if _inicializado:
            return _disponivel

        caminho = os.getenv("FIREBASE_CREDENTIALS_PATH")

        if not caminho or not os.path.exists(caminho):
            _inicializado = True
            return False

        try:
            import firebase_admin
            from firebase_admin import credentials

            credencial = credentials.Certificate(caminho)
            firebase_admin.initialize_app(credencial)
            _disponivel = True
        except Exception:
            # credencial invalida, pacote nao instalado, etc. —
            # notificacao e complemento, nao pode derrubar o backend
            _disponivel = False

        _inicializado = True
        return _disponivel


class NotificacaoService:

    @staticmethod
    def enviar(
        tokens: list[str],
        titulo: str,
        corpo: str,
        dados: dict | None = None,
    ):
        if not tokens or not _garantir_inicializado():
            return

        from firebase_admin import messaging

        for token in tokens:
            try:
                messaging.send(
                    messaging.Message(
                        token=token,
                        notification=messaging.Notification(
                            title=titulo,
                            body=corpo,
                        ),
                        data=dados or {},
                    )
                )
            except Exception:
                # token invalido/expirado ou Firebase fora do ar —
                # nao interrompe o envio pros demais tokens
                pass

    @staticmethod
    def enviar_para_usuario(
        db: Session,
        usuario_id: int,
        titulo: str,
        corpo: str,
        dados: dict | None = None,
    ):
        tokens = DeviceTokenRepository.tokens_de_usuarios(
            db, [usuario_id]
        )
        NotificacaoService.enviar(tokens, titulo, corpo, dados)

    @staticmethod
    def enviar_para_admins(
        db: Session,
        titulo: str,
        corpo: str,
        dados: dict | None = None,
        excluir_usuario_id: int | None = None,
    ):
        query = db.query(User.id).filter(
            User.admin.is_(True),
            User.ativo.is_(True),
        )

        if excluir_usuario_id is not None:
            query = query.filter(User.id != excluir_usuario_id)

        admin_ids = [linha[0] for linha in query.all()]

        tokens = DeviceTokenRepository.tokens_de_usuarios(db, admin_ids)
        NotificacaoService.enviar(tokens, titulo, corpo, dados)
