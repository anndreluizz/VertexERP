from sqlalchemy.orm import Session

from app.models.compra import Compra
from app.models.item_compra import ItemCompra
from app.models.produto import Produto

from app.enums.forma_pagamento import FormaPagamento

from app.repositories.compra_repository import CompraRepository
from app.repositories.item_compra_repository import (
    ItemCompraRepository,
)

from app.services.conta_pagar_service import ContaPagarService


class CompraService:

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return CompraRepository.listar(db, skip, limit)

    @staticmethod
    def buscar(db: Session, compra_id: int):
        return CompraRepository.buscar_por_id(
            db,
            compra_id,
        )

    @staticmethod
    def criar(db: Session, dados):

        try:

            compra = Compra(
                fornecedor_id=dados.fornecedor_id,
                observacao=dados.observacao,
                forma_pagamento=dados.forma_pagamento.value,
                data_vencimento=dados.data_vencimento,
                status="FINALIZADA",
            )

            CompraRepository.criar(
                db,
                compra,
            )

            valor_total = 0

            for item in dados.itens:

                produto = (
                    db.query(Produto)
                    .filter(
                        Produto.id == item.produto_id
                    )
                    .first()
                )

                if not produto:
                    raise Exception(
                        f"Produto {item.produto_id} não encontrado."
                    )

                subtotal = item.valor_unitario * item.quantidade

                novo_item = ItemCompra(
                    compra_id=compra.id,
                    produto_id=item.produto_id,
                    quantidade=item.quantidade,
                    valor_unitario=item.valor_unitario,
                    subtotal=subtotal,
                )

                ItemCompraRepository.criar(
                    db,
                    novo_item,
                )

                produto.estoque += item.quantidade

                valor_total += subtotal

            compra.valor_total = valor_total

            if (
                compra.forma_pagamento
                == FormaPagamento.PRAZO.value
            ):

                ContaPagarService.criar_compra_prazo(
                    db,
                    compra,
                )

            CompraRepository.salvar(db)

            db.refresh(compra)

            return compra

        except Exception:
            db.rollback()
            raise

    @staticmethod
    def excluir(
        db: Session,
        compra_id: int,
    ):

        compra = CompraRepository.buscar_por_id(
            db,
            compra_id,
        )

        if not compra:
            return False

        for item in compra.itens:

            produto = (
                db.query(Produto)
                .filter(
                    Produto.id == item.produto_id
                )
                .first()
            )

            if produto:
                produto.estoque -= item.quantidade

        CompraRepository.excluir(
            db,
            compra,
        )

        return True