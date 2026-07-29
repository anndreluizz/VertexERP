from sqlalchemy.orm import Session

from app.models.venda import Venda
from app.models.item_venda import ItemVenda
from app.models.produto import Produto
from app.models.movimento_estoque import MovimentoEstoque
from app.models.movimento_caixa import MovimentoCaixa
from app.models.movimento_fiado import MovimentoFiado

from app.repositories.venda_repository import VendaRepository
from app.repositories.item_venda_repository import (
    ItemVendaRepository,
)
from app.repositories.caixa_repository import CaixaRepository
from app.repositories.movimento_fiado_repository import (
    MovimentoFiadoRepository,
)

from app.services.movimento_fiado_service import (
    MovimentoFiadoService,
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
        usuario_id: int,
    ):

        caixa = CaixaRepository.buscar_aberto(db)

        if not caixa:
            raise Exception(
                "Não existe caixa aberto. Abra o caixa antes de "
                "registrar uma venda."
            )

        try:

            forma_pagamento = dados.forma_pagamento.value

            if forma_pagamento == "PRAZO" and dados.cliente_id is None:
                raise Exception(
                    "Venda a prazo exige selecionar um cliente."
                )

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

                # Baixa do estoque (automatica, registrada no historico)
                produto.estoque -= item.quantidade

                db.add(produto)

                db.add(
                    MovimentoEstoque(
                        produto_id=produto.id,
                        usuario_id=usuario_id,
                        tipo="SAIDA",
                        quantidade=item.quantidade,
                        motivo=f"Venda #{venda.id}",
                    )
                )

                valor_total += subtotal

            venda.valor_total = (
                valor_total
                - float(dados.desconto)
            )

            db.add(venda)

            # so dinheiro fisico mexe no saldo do caixa; pix/cartao/
            # prazo nao entram na gaveta, mas o movimento fica
            # registrado pra aparecer no fechamento do caixa
            if forma_pagamento == "DINHEIRO":
                caixa.saldo_final += venda.valor_total
                db.add(caixa)

            db.add(
                MovimentoCaixa(
                    caixa_id=caixa.id,
                    usuario_id=usuario_id,
                    tipo="VENDA",
                    valor=venda.valor_total,
                    forma_pagamento=forma_pagamento,
                    descricao=f"Venda #{venda.id}",
                )
            )

            # venda a prazo vira lancamento de compra no caderninho
            # do cliente (mesma transacao, atomico com o resto)
            if forma_pagamento == "PRAZO":
                MovimentoFiadoService.criar_compra_da_venda(
                    db,
                    venda,
                    usuario_id,
                )

            db.commit()

            db.refresh(venda)

            return venda

        except Exception as e:

            db.rollback()

            raise Exception(str(e))

    @staticmethod
    def excluir(
        db: Session,
        venda_id: int,
        usuario_id: int,
    ):

        venda = VendaRepository.buscar_por_id(
            db,
            venda_id,
        )

        if venda is None:
            return False

        # Devolve o estoque (automatico, registrado no historico)
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

                db.add(
                    MovimentoEstoque(
                        produto_id=produto.id,
                        usuario_id=usuario_id,
                        tipo="ENTRADA",
                        quantidade=item.quantidade,
                        motivo=f"Estorno da venda #{venda_id}",
                    )
                )

        # Estorna o valor no caixa aberto, se a venda tiver sido
        # em dinheiro (pix/cartao/prazo nao afetam a gaveta fisica)
        if venda.forma_pagamento == "DINHEIRO":

            caixa = CaixaRepository.buscar_aberto(db)

            if caixa:

                caixa.saldo_final -= venda.valor_total
                db.add(caixa)

                db.add(
                    MovimentoCaixa(
                        caixa_id=caixa.id,
                        usuario_id=usuario_id,
                        tipo="ESTORNO",
                        valor=-venda.valor_total,
                        forma_pagamento=venda.forma_pagamento,
                        descricao=f"Estorno da venda #{venda_id}",
                    )
                )

        # Zera a divida do caderninho, se a venda tiver sido a prazo.
        # Se o cliente ja tiver pago parte do saldo (de forma geral,
        # nao especifica dessa venda - o caderninho e um saldo unico
        # corrido), o estorno nao pode "devolver" mais do que ele
        # ainda deve, senao o saldo fica negativo indevidamente.
        if venda.forma_pagamento == "PRAZO" and venda.cliente_id:

            saldo_atual = MovimentoFiadoRepository.saldo_por_cliente(
                db,
                venda.cliente_id,
            )

            valor_estorno = min(venda.valor_total, saldo_atual)

            if valor_estorno > 0:

                db.add(
                    MovimentoFiado(
                        cliente_id=venda.cliente_id,
                        venda_id=None,
                        usuario_id=usuario_id,
                        tipo="PAGAMENTO",
                        valor=valor_estorno,
                        descricao=f"Estorno da venda #{venda_id}",
                    )
                )

        # Garante que nenhum lancamento antigo do fiado fique
        # apontando pra essa venda antes de apaga-la
        db.query(MovimentoFiado).filter(
            MovimentoFiado.venda_id == venda_id
        ).update({"venda_id": None})

        VendaRepository.excluir(
            db,
            venda,
        )

        db.commit()

        return True