from sqlalchemy.orm import Session

from app.models.conta_receber import ContaReceber


class ContaReceberRepository:

    @staticmethod
    def criar(db: Session, conta: ContaReceber):
        db.add(conta)
        db.commit()
        db.refresh(conta)
        return conta

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return (
            db.query(ContaReceber)
            .order_by(ContaReceber.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def buscar_por_id(
        db: Session,
        conta_id: int
    ):
        return (
            db.query(ContaReceber)
            .filter(ContaReceber.id == conta_id)
            .first()
        )

    @staticmethod
    def listar_por_cliente(
        db: Session,
        cliente_id: int,
        skip: int = 0,
        limit: int = 100,
    ):
        return (
            db.query(ContaReceber)
            .filter(
                ContaReceber.cliente_id == cliente_id
            )
            .order_by(
                ContaReceber.data_vencimento
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
            db.query(ContaReceber)
            .filter(
                ContaReceber.status == "PENDENTE"
            )
            .order_by(
                ContaReceber.data_vencimento
            )
            .all()
        )

    @staticmethod
    def listar_recebidas(db: Session, skip: int = 0, limit: int = 100):
        return (
            db.query(ContaReceber)
            .filter(
                ContaReceber.status == "RECEBIDO"
            )
            .order_by(
                ContaReceber.data_recebimento.desc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def atualizar(
        db: Session,
        conta: ContaReceber
    ):
        db.commit()
        db.refresh(conta)
        return conta

    @staticmethod
    def excluir(
        db: Session,
        conta: ContaReceber
    ):
        db.delete(conta)
        db.commit()