from sqlalchemy.orm import Session

from app.models.compra import Compra
from app.models.item_compra import ItemCompra
from app.models.produto import Produto

from app.enums.forma_pagamento import FormaPagamento

from app.repositories.compra_repository import CompraRepository
from app.repositories.item_compra_repository import (
    ItemCompraRepository,
)

from app.schemas.movimento_estoque import MovimentoEstoqueCreate
from app.services.conta_pagar_service import ContaPagarService
from app.services.movimento_estoque_service import MovimentoEstoqueService


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
    def criar(
        db: Session,
        dados,
        usuario_id: int,
        loja_id: int | None = None,
        fornecedor_nome: str | None = None,
    ):

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

                # entrada real de estoque, com historico (MovimentoEstoque)
                # -- nunca mais mutar produto.estoque direto, isso e' do
                # tempo antes do sistema multi-loja (ver EstoqueLojaRepository)
                MovimentoEstoqueService.criar(
                    db,
                    MovimentoEstoqueCreate(
                        produto_id=produto.id,
                        tipo="ENTRADA",
                        quantidade=item.quantidade,
                        motivo=(
                            f"Compra #{compra.id}"
                            + (f" — {fornecedor_nome}" if fornecedor_nome else "")
                        ),
                    ),
                    usuario_id,
                    loja_id,
                )

                valor_total += subtotal

            compra.valor_total = valor_total

            if (
                compra.forma_pagamento
                == FormaPagamento.PRAZO.value
            ):

                ContaPagarService.criar_compra_prazo(
                    db,
                    compra,
                    usuario_id,
                    loja_id,
                )

            CompraRepository.salvar(db)

            db.refresh(compra)

            return compra

        except Exception:
            db.rollback()
            raise

    @staticmethod
    def cancelar(
        db: Session,
        compra_id: int,
        usuario_id: int,
        loja_id: int | None = None,
    ):
        from datetime import datetime

        compra = CompraRepository.buscar_por_id(
            db,
            compra_id,
        )

        if not compra:
            return False

        if compra.status == "CANCELADA":
            raise Exception("Essa compra já está cancelada.")

        for item in compra.itens:

            MovimentoEstoqueService.criar(
                db,
                MovimentoEstoqueCreate(
                    produto_id=item.produto_id,
                    tipo="SAIDA",
                    quantidade=item.quantidade,
                    motivo=f"Cancelamento da Compra #{compra.id}",
                ),
                usuario_id,
                loja_id,
            )

        compra.status = "CANCELADA"
        compra.cancelado_em = datetime.utcnow()

        CompraRepository.salvar(db)

        return True
