from sqlalchemy.orm import Session

from app.models.cliente_observacao import ClienteObservacao
from app.schemas.cliente import ClienteObservacaoCreate


class ClienteObservacaoService:

    @staticmethod
    def listar(db: Session, cliente_id: int):
        return (
            db.query(ClienteObservacao)
            .filter(ClienteObservacao.cliente_id == cliente_id)
            .order_by(ClienteObservacao.criado_em.desc())
            .all()
        )

    @staticmethod
    def criar(
        db: Session,
        cliente_id: int,
        dados: ClienteObservacaoCreate,
        usuario_id: int,
    ):
        texto = dados.texto.strip()

        if not texto:
            raise ValueError("A observação não pode ficar em branco.")

        observacao = ClienteObservacao(
            cliente_id=cliente_id,
            usuario_id=usuario_id,
            texto=texto,
        )

        db.add(observacao)
        db.commit()
        db.refresh(observacao)

        return observacao

    @staticmethod
    def excluir(db: Session, cliente_id: int, observacao_id: int):
        observacao = (
            db.query(ClienteObservacao)
            .filter(
                ClienteObservacao.id == observacao_id,
                ClienteObservacao.cliente_id == cliente_id,
            )
            .first()
        )

        if not observacao:
            raise ValueError("Observação não encontrada.")

        db.delete(observacao)
        db.commit()

        return {"mensagem": "Observação excluída com sucesso."}
