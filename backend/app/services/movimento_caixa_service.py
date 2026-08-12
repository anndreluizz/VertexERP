from sqlalchemy.orm import Session

from app.models.movimento_caixa import MovimentoCaixa
from app.repositories.caixa_repository import CaixaRepository
from app.repositories.movimento_caixa_repository import (
    MovimentoCaixaRepository,
)
from app.schemas.movimento_caixa import MovimentoCaixaCreate


class MovimentoCaixaService:

    @staticmethod
    def criar(
        db: Session,
        dados: MovimentoCaixaCreate,
        usuario_id: int,
    ):

        caixa = CaixaRepository.buscar_aberto(db, usuario_id)

        if not caixa:
            raise Exception("Não existe caixa aberto.")

        movimento = MovimentoCaixa(
            caixa_id=caixa.id,
            usuario_id=usuario_id,
            tipo=dados.tipo.upper(),
            descricao=dados.descricao,
            valor=dados.valor,
        )

        if movimento.tipo in [
            "ENTRADA",
            "SUPRIMENTO",
            "VENDA",
            "RECEBIMENTO",
        ]:
            caixa.saldo_final += movimento.valor

        elif movimento.tipo in [
            "SAIDA",
            "SANGRIA",
            "PAGAMENTO",
        ]:
            caixa.saldo_final -= movimento.valor

        CaixaRepository.atualizar(db, caixa)

        return MovimentoCaixaRepository.criar(
            db,
            movimento
        )

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return MovimentoCaixaRepository.listar(db, skip, limit)

    @staticmethod
    def listar_por_caixa(
        db: Session,
        caixa_id: int,
        skip: int = 0,
        limit: int = 100,
    ):
        return MovimentoCaixaRepository.listar_por_caixa(
            db,
            caixa_id
        )