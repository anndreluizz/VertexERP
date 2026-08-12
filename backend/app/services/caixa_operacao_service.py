from sqlalchemy.orm import Session

from app.models.caixa import Caixa
from app.models.movimento_caixa import MovimentoCaixa


class CaixaOperacaoService:

    @staticmethod
    def buscar_caixa_aberto(db: Session, usuario_id: int):

        return (
            db.query(Caixa)
            .filter(Caixa.status == "ABERTO")
            .filter(Caixa.usuario_id == usuario_id)
            .first()
        )

    @staticmethod
    def registrar_movimento(
        db: Session,
        caixa: Caixa,
        usuario_id: int,
        tipo: str,
        descricao: str,
        valor: float,
        venda_id: int | None = None,
    ):

        movimento = MovimentoCaixa(
            caixa_id=caixa.id,
            usuario_id=usuario_id,
            tipo=tipo,
            descricao=descricao,
            valor=valor,
            venda_id=venda_id,
        )

        db.add(movimento)

        caixa.saldo_final += valor

        db.commit()
        db.refresh(movimento)

        return movimento

    @staticmethod
    def registrar_recebimento(
        db: Session,
        usuario_id: int,
        valor: float,
        descricao: str,
    ):

        caixa = CaixaOperacaoService.buscar_caixa_aberto(db, usuario_id)

        if not caixa:
            raise Exception("Nenhum caixa aberto.")

        return CaixaOperacaoService.registrar_movimento(
            db=db,
            caixa=caixa,
            usuario_id=usuario_id,
            tipo="RECEBIMENTO",
            descricao=descricao,
            valor=valor,
        )