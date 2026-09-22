from sqlalchemy.orm import Session

from app.models.notificacao import Notificacao


class NotificacaoRepository:

    @staticmethod
    def criar_lote(db: Session, notificacoes: list[Notificacao]):
        db.add_all(notificacoes)
        db.commit()

    @staticmethod
    def listar(db: Session, usuario_id: int, skip: int = 0, limit: int = 50):
        return (
            db.query(Notificacao)
            .filter(Notificacao.usuario_id == usuario_id)
            .order_by(Notificacao.criado_em.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def contar_nao_lidas(db: Session, usuario_id: int) -> int:
        return (
            db.query(Notificacao)
            .filter(
                Notificacao.usuario_id == usuario_id,
                Notificacao.lida.is_(False),
            )
            .count()
        )

    @staticmethod
    def buscar_por_id(db: Session, notificacao_id: int, usuario_id: int):
        return (
            db.query(Notificacao)
            .filter(
                Notificacao.id == notificacao_id,
                Notificacao.usuario_id == usuario_id,
            )
            .first()
        )

    @staticmethod
    def marcar_todas_lidas(db: Session, usuario_id: int):
        db.query(Notificacao).filter(
            Notificacao.usuario_id == usuario_id,
            Notificacao.lida.is_(False),
        ).update({"lida": True})
        db.commit()

    @staticmethod
    def salvar(db: Session):
        db.commit()
