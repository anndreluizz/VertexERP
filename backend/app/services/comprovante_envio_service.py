from sqlalchemy.orm import Session

from app.models.comprovante_envio import ComprovanteEnvio
from app.repositories.comprovante_envio_repository import (
    ComprovanteEnvioRepository,
)


class ComprovanteEnvioService:

    @staticmethod
    def registrar(
        db: Session,
        venda_id: int,
        canal: str,
        destino: str,
        status: str,
        usuario_id: int | None = None,
        erro: str | None = None,
    ):
        """Sempre registra, mesmo quando o envio falhou -- o
        histórico da falha importa tanto quanto o do sucesso pra quem
        for conferir depois se o cliente recebeu ou não. Nunca é
        apagado (ver models/comprovante_envio.py)."""

        envio = ComprovanteEnvio(
            venda_id=venda_id,
            usuario_id=usuario_id,
            canal=canal,
            destino=destino,
            status=status,
            erro=erro,
        )

        return ComprovanteEnvioRepository.criar(db, envio)

    @staticmethod
    def listar_por_venda(db: Session, venda_id: int):
        return ComprovanteEnvioRepository.listar_por_venda(db, venda_id)
