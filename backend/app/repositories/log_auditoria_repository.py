from sqlalchemy.orm import Session

from app.models.log_auditoria import LogAuditoria


class LogAuditoriaRepository:

    @staticmethod
    def criar(db: Session, log: LogAuditoria):
        db.add(log)
        db.commit()
        return log

    @staticmethod
    def listar(
        db: Session,
        usuario_id: int | None = None,
        acao: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        query = db.query(LogAuditoria)

        if usuario_id is not None:
            query = query.filter(LogAuditoria.usuario_id == usuario_id)

        if acao is not None:
            query = query.filter(LogAuditoria.acao == acao)

        return (
            query.order_by(LogAuditoria.data.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
