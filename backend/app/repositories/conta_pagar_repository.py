from sqlalchemy.orm import Session

from app.models.conta_pagar import ContaPagar
from app.enums.status_conta_pagar import StatusContaPagar


class ContaPagarRepository:

    @staticmethod
    def criar(db: Session, conta: ContaPagar):
        db.add(conta)
        db.commit()
        db.refresh(conta)
        return conta

    @staticmethod
    def atualizar(db: Session, conta: ContaPagar):
        db.commit()
        db.refresh(conta)
        return conta

    @staticmethod
    def excluir(db: Session, conta: ContaPagar):
        db.delete(conta)
        db.commit()

    @staticmethod
    def buscar_por_id(
        db: Session,
        conta_id: int,
    ):
        return (
            db.query(ContaPagar)
            .filter(
                ContaPagar.id == conta_id
            )
            .first()
        )

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100, loja_id: int | None = None):
        query = db.query(ContaPagar)

        if loja_id is not None:
            query = query.filter(ContaPagar.loja_id == loja_id)

        return (
            query
            .order_by(
                ContaPagar.data_vencimento
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def listar_pendentes(db: Session):
        # Sem paginação: usado internamente por FinanceiroService.fluxo_caixa,
        # que precisa do total real de contas pendentes para o cálculo do
        # saldo projetado, não só da primeira página.
        return (
            db.query(ContaPagar)
            .filter(
                ContaPagar.status == StatusContaPagar.PENDENTE.value
            )
            .all()
        )

    @staticmethod
    def listar_pagas(db: Session, skip: int = 0, limit: int = 100):
        return (
            db.query(ContaPagar)
            .filter(
                ContaPagar.status == StatusContaPagar.PAGO.value
            )
            .offset(skip)
            .limit(limit)
            .all()
        )