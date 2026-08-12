from sqlalchemy.orm import Session

from app.enums.forma_pagamento import FormaPagamento
from app.enums.tipo_movimento_caixa import TipoMovimentoCaixa

from app.models.venda import Venda
from app.models.item_venda import ItemVenda
from app.models.produto import Produto

from app.repositories.venda_repository import VendaRepository
from app.repositories.item_venda_repository import (
    ItemVendaRepository,
)
from app.repositories.movimento_caixa_repository import (
    MovimentoCaixaRepository,
)

from app.services.caixa_operacao_service import CaixaOperacaoService
from app.services.conta_receber_service import (
    ContaReceberService,
)
from app.services.fiado_service import FiadoService


class VendaService:

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return VendaRepository.listar(db, skip, limit)

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

        caixa = None

        if dados.forma_pagamento != FormaPagamento.PRAZO:

            # Fiado não passa dinheiro na hora, então não depende do caixa
            # do dia — as demais formas de pagamento precisam de um caixa
            # aberto pra a venda entrar no fechamento de verdade.
            caixa = CaixaOperacaoService.buscar_caixa_aberto(db)

            if caixa is None:
                raise Exception(
                    "Não é possível finalizar a venda: nenhum caixa está "
                    "aberto. Abra o caixa antes de vender (ou use Prazo/"
                    "Fiado, que não exige caixa aberto)."
                )

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

            descricoes_itens = []

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

                descricoes_itens.append(
                    f"{item.quantidade}x {produto.nome}"
                )

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

                FiadoService.registrar_compra(
                    db,
                    venda.cliente_id,
                    venda.valor_total,
                    ", ".join(descricoes_itens),
                    venda.id,
                    usuario_id,
                )

            else:

                CaixaOperacaoService.registrar_movimento(
                    db=db,
                    caixa=caixa,
                    usuario_id=usuario_id,
                    tipo=TipoMovimentoCaixa.VENDA.value,
                    descricao=f"Venda #{venda.id}",
                    valor=venda.valor_total,
                    venda_id=venda.id,
                )

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

        movimento_original = (
            MovimentoCaixaRepository.buscar_movimento_venda(
                db,
                venda_id,
            )
        )

        # Se a venda gerou um lançamento de caixa e esse caixa já foi
        # fechado, cancelar aqui mexeria no saldo de um caixa que já foi
        # conferido/fechado — bloqueia e pede ajuste manual em vez de
        # reescrever um fechamento que já aconteceu.
        if (
            movimento_original is not None
            and movimento_original.caixa.status != "ABERTO"
        ):
            raise Exception(
                "Não é possível cancelar esta venda: o caixa em que ela "
                "foi lançada já está fechado. Registre um ajuste manual "
                "no caixa atual, se necessário."
            )

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

        if movimento_original is not None:

            CaixaOperacaoService.registrar_movimento(
                db=db,
                caixa=movimento_original.caixa,
                usuario_id=usuario_id,
                tipo=TipoMovimentoCaixa.ESTORNO.value,
                descricao=f"Estorno da Venda #{venda.id}",
                valor=-movimento_original.valor,
                venda_id=venda.id,
            )

        VendaRepository.excluir(
            db,
            venda,
        )

        db.commit()

        return True