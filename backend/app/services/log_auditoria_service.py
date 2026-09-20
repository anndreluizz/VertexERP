from sqlalchemy.orm import Session

from app.models.log_auditoria import LogAuditoria
from app.repositories.log_auditoria_repository import (
    LogAuditoriaRepository,
)


class LogAuditoriaService:

    @staticmethod
    def registrar(
        db: Session,
        usuario_id: int | None,
        acao: str,
        ip: str | None = None,
        detalhes: str | None = None,
    ):
        log = LogAuditoria(
            usuario_id=usuario_id,
            acao=acao,
            ip=ip,
            detalhes=detalhes,
        )
        return LogAuditoriaRepository.criar(db, log)

    @staticmethod
    def listar(
        db: Session,
        usuario_id: int | None = None,
        acao: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        return LogAuditoriaRepository.listar(
            db, usuario_id, acao, skip, limit
        )
