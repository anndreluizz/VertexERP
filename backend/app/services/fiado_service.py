from datetime import datetime

from sqlalchemy.orm import Session

from app.models.movimento_fiado import MovimentoFiado
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.movimento_fiado_repository import (
    MovimentoFiadoRepository,
)


class FiadoService:

    @staticmethod
    def registrar_compra(
        db: Session,
        cliente_id: int,
        valor: float,
        descricao: str,
        venda_id: int,
        usuario_id: int,
    ):
        movimento = MovimentoFiado(
            cliente_id=cliente_id,
            venda_id=venda_id,
            usuario_id=usuario_id,
            tipo="COMPRA",
            valor=valor,
            descricao=descricao,
        )

        return MovimentoFiadoRepository.criar(db, movimento)

    @staticmethod
    def registrar_compra_manual(
        db: Session,
        cliente_id: int,
        valor: float,
        descricao: str | None,
        data: datetime | None,
        usuario_id: int,
    ):
        cliente = ClienteRepository.buscar_por_id(db, cliente_id)

        if not cliente:
            raise Exception("Cliente não encontrado.")

        if valor <= 0:
            raise Exception("Informe um valor de compra maior que zero.")

        movimento = MovimentoFiado(
            cliente_id=cliente_id,
            venda_id=None,
            usuario_id=usuario_id,
            tipo="COMPRA",
            valor=valor,
            descricao=descricao,
        )

        if data is not None:
            movimento.data = data

        return MovimentoFiadoRepository.criar(db, movimento)

    @staticmethod
    def registrar_pagamento(
        db: Session,
        cliente_id: int,
        valor: float,
        descricao: str | None,
        usuario_id: int,
        data: datetime | None = None,
    ):
        cliente = ClienteRepository.buscar_por_id(db, cliente_id)

        if not cliente:
            raise Exception("Cliente não encontrado.")

        if valor <= 0:
            raise Exception("Informe um valor de pagamento maior que zero.")

        movimento = MovimentoFiado(
            cliente_id=cliente_id,
            venda_id=None,
            usuario_id=usuario_id,
            tipo="PAGAMENTO",
            valor=valor,
            descricao=descricao,
        )

        if data is not None:
            movimento.data = data

        return MovimentoFiadoRepository.criar(db, movimento)

    @staticmethod
    def ficha_cliente(db: Session, cliente_id: int):
        cliente = ClienteRepository.buscar_por_id(db, cliente_id)

        if not cliente:
            raise Exception("Cliente não encontrado.")

        movimentos = MovimentoFiadoRepository.listar_por_cliente(
            db, cliente_id
        )

        saldo = 0.0

        for movimento in movimentos:
            if movimento.tipo == "COMPRA":
                saldo += movimento.valor
            else:
                saldo -= movimento.valor

        return {
            "cliente_id": cliente.id,
            "nome": cliente.nome,
            "saldo_devedor": saldo,
            "movimentos": movimentos,
        }

    @staticmethod
    def saldos_por_cliente(db: Session):
        return MovimentoFiadoRepository.saldos_por_cliente(db)
