from sqlalchemy.orm import Session

from app.enums.forma_pagamento import FormaPagamento

from app.models.venda import Venda
from app.models.item_venda import ItemVenda
from app.models.produto import Produto

from app.repositories.venda_repository import VendaRepository
from app.repositories.item_venda_repository import (
    ItemVendaRepository,
)

from app.services.conta_receber_service import (
    ContaReceberService,
)


class VendaService:

    @staticmethod
    def listar(db: Session):
        return VendaRepository.listar(db)

    @staticmethod
    def buscar(
        db: Session,
        venda_id: int,
    ):
        return VendaRepository.buscar_por_id(
            db,
            venda_id,
        )

    @staticmethod
    def criar(
        db: Session,
        dados,
    ):

        try:

            venda = Venda(
                cliente_id=dados.cliente_id,
                observacao=dados.observacao,
                desconto=float(dados.desconto),
                forma_pagamento=dados.forma_pagamento.value,
                data_vencimento=dados.data_vencimento,
                status="FINALIZADA",
            )

            VendaRepository.criar(
                db,
                venda,
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

                if produto is None:
                    raise Exception(
                        f"Produto {item.produto_id} não encontrado."
                    )

                if produto.estoque < item.quantidade:
                    raise Exception(
                        f"Estoque insuficiente para {produto.nome}."
                    )

                subtotal = (
                    float(item.valor_unitario)
                    * item.quantidade
                )

                item_venda = ItemVenda(
                    venda_id=venda.id,
                    produto_id=produto.id,
                    quantidade=item.quantidade,
                    valor_unitario=float(
                        item.valor_unitario
                    ),
                    subtotal=subtotal,
                )

                ItemVendaRepository.criar(
                    db,
                    item_venda,
                )

                # Baixa do estoque
                produto.estoque -= item.quantidade

                db.add(produto)

                valor_total += subtotal

            venda.valor_total = (
                valor_total
                - float(dados.desconto)
            )

            db.add(venda)

            db.commit()

            db.refresh(venda)

            if (
                dados.forma_pagamento
                == FormaPagamento.PRAZO
            ):

                ContaReceberService.criar_venda_prazo(
                    db,
                    venda,
                )

            return venda

        except Exception as e:

            db.rollback()

            raise Exception(str(e))

    @staticmethod
    def excluir(
        db: Session,
        venda_id: int,
    ):

        venda = VendaRepository.buscar_por_id(
            db,
            venda_id,
        )

        if venda is None:
            return False

        # Devolve o estoque
        for item in venda.itens:

            produto = (
                db.query(Produto)
                .filter(
                    Produto.id == item.produto_id
                )
                .first()
            )

            if produto:

                produto.estoque += item.quantidade

                db.add(produto)

        VendaRepository.excluir(
            db,
            venda,
        )

        db.commit()

        return True