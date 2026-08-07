from sqlalchemy.orm import Session

from app.models.comprovante_envio import ComprovanteEnvio


class ComprovanteEnvioRepository:

    @staticmethod
    def criar(db: Session, envio: ComprovanteEnvio):
        db.add(envio)
        db.commit()
        db.refresh(envio)
        return envio

    @staticmethod
    def listar_por_venda(db: Session, venda_id: int):
        return (
            db.query(ComprovanteEnvio)
            .filter(ComprovanteEnvio.venda_id == venda_id)
            .order_by(ComprovanteEnvio.data.desc())
            .all()
        )
