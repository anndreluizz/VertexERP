from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.movimento_fiado import MovimentoFiado


class MovimentoFiadoRepository:

    @staticmethod
    def criar(db: Session, movimento: MovimentoFiado):
        db.add(movimento)
        db.commit()
        db.refresh(movimento)
        return movimento

    @staticmethod
    def listar(db: Session):
        return (
            db.query(MovimentoFiado)
            .order_by(MovimentoFiado.data.desc())
            .all()
        )

    @staticmethod
    def buscar_por_id(db: Session, movimento_id: int):
        return (
            db.query(MovimentoFiado)
            .filter(MovimentoFiado.id == movimento_id)
            .first()
        )

    @staticmethod
    def atualizar(db: Session, movimento: MovimentoFiado):
        db.commit()
        db.refresh(movimento)
        return movimento

    @staticmethod
    def excluir(db: Session, movimento: MovimentoFiado):
        db.delete(movimento)
        db.commit()

    @staticmethod
    def listar_por_cliente(db: Session, cliente_id: int):
        return (
            db.query(MovimentoFiado)
            .filter(MovimentoFiado.cliente_id == cliente_id)
            .order_by(MovimentoFiado.data)
            .all()
        )

    @staticmethod
    def saldo_por_cliente(db: Session, cliente_id: int) -> Decimal:
        valor_assinado = case(
            (MovimentoFiado.tipo == "COMPRA", MovimentoFiado.valor),
            else_=-MovimentoFiado.valor,
        )

        saldo = (
            db.query(func.sum(valor_assinado))
            .filter(MovimentoFiado.cliente_id == cliente_id)
            .scalar()
        )

        return saldo or Decimal("0")

    @staticmethod
    def listar_parados(db: Session, dias_limite: int):
        """Um cliente por linha (cliente_id, saldo, ultima_movimentacao)
        pra quem tem saldo devedor > 0 e nao mexe no fiado ha pelo
        menos `dias_limite` dias -- usado pelo lembrete automatico de
        WhatsApp (ver whatsapp_lembrete_service.py). Feito com HAVING
        em vez de trazer tudo pra memoria e filtrar em Python, porque
        essa lista pode crescer bastante numa loja com muitos
        clientes fiado."""

        valor_assinado = case(
            (MovimentoFiado.tipo == "COMPRA", MovimentoFiado.valor),
            else_=-MovimentoFiado.valor,
        )

        # comparado em Python (naive, hora local), mesmo padrao de
        # datetime.now() usado no resto do projeto -- evita
        # depender de conversao implicita de timezone do Postgres
        # entre timestamp naive e now() (timestamptz).
        limite = datetime.now() - timedelta(days=dias_limite)

        return (
            db.query(
                MovimentoFiado.cliente_id,
                func.sum(valor_assinado).label("saldo"),
                func.max(MovimentoFiado.data).label("ultima_movimentacao"),
            )
            .group_by(MovimentoFiado.cliente_id)
            .having(func.sum(valor_assinado) > 0)
            .having(func.max(MovimentoFiado.data) <= limite)
            .all()
        )

    @staticmethod
    def saldos_por_cliente(db: Session) -> dict:
        """Saldo devedor de cada cliente que já teve pelo menos um
        movimento, numa única query agrupada -- evita fazer uma
        consulta por cliente (N+1) quando a tela precisa listar vários
        de uma vez. Cliente sem nenhum movimento simplesmente não
        aparece no dicionário."""

        valor_assinado = case(
            (MovimentoFiado.tipo == "COMPRA", MovimentoFiado.valor),
            else_=-MovimentoFiado.valor,
        )

        linhas = (
            db.query(
                MovimentoFiado.cliente_id,
                func.sum(valor_assinado).label("saldo"),
            )
            .group_by(MovimentoFiado.cliente_id)
            .all()
        )

        return {linha.cliente_id: linha.saldo for linha in linhas}

    @staticmethod
    def saldo_total(db: Session) -> Decimal:
        """Soma o fiado em aberto de TODOS os clientes numa unica query
        -- mesmo criterio de saldo_por_cliente, so sem o filtro de
        cliente. Usado no KPI 'Contas a receber' do dashboard (a tabela
        ContaReceber legada nao e mais alimentada desde que fiado passou
        a usar MovimentoFiado)."""

        valor_assinado = case(
            (MovimentoFiado.tipo == "COMPRA", MovimentoFiado.valor),
            else_=-MovimentoFiado.valor,
        )

        saldo = db.query(func.sum(valor_assinado)).scalar()

        return saldo or Decimal("0")
