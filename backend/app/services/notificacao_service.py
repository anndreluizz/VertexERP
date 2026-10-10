import os
import threading

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.notificacao import Notificacao
from app.repositories.device_token_repository import DeviceTokenRepository
from app.repositories.notificacao_repository import NotificacaoRepository

_lock = threading.Lock()


def moeda(valor) -> str:
    """R$ 1.234,56 -- formato brasileiro pro texto das notificacoes."""
    return f"R$ {float(valor):,.2f}".replace(",", "_").replace(
        ".", ","
    ).replace("_", ".")
def nome_do_usuario(db: Session, usuario_id) -> str:
    """Primeiro nome de quem fez a acao, pro texto da notificacao."""
    usuario = db.query(User).filter(User.id == usuario_id).first() if usuario_id else None
    nome = (usuario.nome or "").strip() if usuario else ""
    return nome.split()[0].title() if nome else "Alguém"


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
        if not tokens:
            return

        # Em segundo plano: e' chamado de dentro de requisicoes criticas
        # (ex.: finalizar venda, 2x por venda). Com a internet lenta, o
        # Firebase segurava a resposta alem do timeout do PDV -> o caixa
        # via "erro", reenviava, e a venda (ja gravada) saia em dobro.
        threading.Thread(
            target=NotificacaoService._enviar_agora,
            args=(tokens, titulo, corpo, dados),
            daemon=True,
        ).start()

    @staticmethod
    def _enviar_agora(tokens, titulo, corpo, dados):
        if not _garantir_inicializado():
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
        NotificacaoService._persistir(db, [usuario_id], titulo, corpo)

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

        NotificacaoService._persistir(db, admin_ids, titulo, corpo)

        tokens = DeviceTokenRepository.tokens_de_usuarios(db, admin_ids)
        NotificacaoService.enviar(tokens, titulo, corpo, dados)

    @staticmethod
    def _persistir(db: Session, usuario_ids: list[int], titulo: str, corpo: str):
        """Central de notificacoes do desktop (sem device token/push
        nenhum, so' o mobile tem) -- salva uma linha por destinatario,
        independente do Firebase estar configurado ou nao."""

        if not usuario_ids:
            return

        NotificacaoRepository.criar_lote(db, [
            Notificacao(usuario_id=usuario_id, titulo=titulo, corpo=corpo)
            for usuario_id in usuario_ids
        ])
