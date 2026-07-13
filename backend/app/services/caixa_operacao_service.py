from sqlalchemy.orm import Session

from app.models.caixa import Caixa
from app.models.movimento_caixa import MovimentoCaixa


class CaixaOperacaoService:

    @staticmethod
    def buscar_caixa_aberto(db: Session):

        return (
            db.query(Caixa)
            .filter(Caixa.status == "ABERTO")
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
    ):

        movimento = MovimentoCaixa(
            caixa_id=caixa.id,
            usuario_id=usuario_id,
            tipo=tipo,
            descricao=descricao,
            valor=valor,
        )

        db.add(movimento)

        caixa.saldo_final += valor

        db.flush()

        return movimento

    @staticmethod
    def registrar_recebimento(
        db: Session,
        usuario_id: int,
        valor: float,
        descricao: str,
    ):

        caixa = CaixaOperacaoService.buscar_caixa_aberto(db)

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