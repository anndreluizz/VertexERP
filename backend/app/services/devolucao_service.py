from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.utils.quantidade import formatar_quantidade
from app.enums.status_venda import StatusVenda
from app.models.devolucao import Devolucao, ItemDevolucao
from app.models.movimento_caixa import MovimentoCaixa
from app.models.movimento_estoque import MovimentoEstoque
from app.models.movimento_fiado import MovimentoFiado
from app.models.produto import Produto
from app.models.venda import Venda
from app.repositories.caixa_repository import CaixaRepository
from app.repositories.estoque_loja_repository import EstoqueLojaRepository
from app.repositories.movimento_fiado_repository import MovimentoFiadoRepository
from app.services.notificacao_service import (
    NotificacaoService,
    moeda,
    nome_do_usuario,
)
from app.services.venda_service import _itens_para_baixa_estoque

_FORMAS_REEMBOLSO = {"DINHEIRO", "PIX", "DEBITO", "CREDITO", "PRAZO"}

_CENTAVO = Decimal("0.01")


def quantidades_devolvidas(db: Session, venda_id: int) -> dict[int, int]:
    """item_venda_id -> quantidade já devolvida (somando todas as
    devoluções dessa venda)."""

    linhas = (
        db.query(ItemDevolucao.item_venda_id, func.sum(ItemDevolucao.quantidade))
        .join(Devolucao, Devolucao.id == ItemDevolucao.devolucao_id)
        .filter(Devolucao.venda_id == venda_id)
        .group_by(ItemDevolucao.item_venda_id)
        .all()
    )

    return {item_id: qtd for item_id, qtd in linhas}


def valor_devolvido(db: Session, venda_id: int) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(Devolucao.valor_total), 0))
        .filter(Devolucao.venda_id == venda_id)
        .scalar()
    )
    return Decimal(total)


class DevolucaoService:

    @staticmethod
    def listar_da_venda(db: Session, venda_id: int):
        return (
            db.query(Devolucao)
            .filter(Devolucao.venda_id == venda_id)
            .order_by(Devolucao.id)
            .all()
        )

    @staticmethod
    def criar(db: Session, venda_id: int, dados, usuario_id: int):
        """Devolve parte dos itens de uma venda finalizada: o estoque
        volta, e o valor (proporcional ao desconto/acréscimo da venda)
        sai do caixa pela forma escolhida, ou é abatido do fiado
        (forma PRAZO). Tudo numa transação só."""

        # FOR UPDATE: duas devoluções simultâneas da mesma venda
        # passariam as duas pela checagem de quantidade restante
        venda = (
            db.query(Venda).filter(Venda.id == venda_id).with_for_update().first()
        )

        if venda is None:
            return None

        if venda.status != StatusVenda.FINALIZADA.value:
            raise Exception("Só dá pra devolver itens de uma venda finalizada.")

        forma = dados.forma_reembolso.value

        if forma not in _FORMAS_REEMBOLSO:
            raise Exception("Forma de devolução inválida.")

        if forma == "PRAZO" and not venda.cliente_id:
            raise Exception(
                "Essa venda não tem cliente -- não dá pra abater do fiado."
            )

        if not dados.itens:
            raise Exception("Escolha pelo menos um item para devolver.")

        caixa = CaixaRepository.buscar_aberto(
            db, usuario_id, venda.loja_id, para_atualizar=True
        )

        if not caixa:
            raise Exception(
                "Não existe caixa aberto. Abra o caixa antes de "
                "registrar a devolução."
            )

        itens_venda = {item.id: item for item in venda.itens}
        ja_devolvido = quantidades_devolvidas(db, venda.id)

        # valor de cada item já com o desconto/acréscimo da venda
        # rateado: total da venda / soma dos subtotais
        soma_subtotais = sum((item.subtotal for item in venda.itens), Decimal("0"))
        fator = (
            Decimal(venda.valor_total) / soma_subtotais
            if soma_subtotais > 0 else Decimal("0")
        )

        devolucao = Devolucao(
            venda_id=venda.id,
            usuario_id=usuario_id,
            forma_reembolso=forma,
            motivo=dados.motivo,
            valor_total=Decimal("0"),
        )

        total = Decimal("0")
        vistos = set()

        for pedido in dados.itens:

            item = itens_venda.get(pedido.item_venda_id)

            if item is None:
                raise Exception("Item não pertence a essa venda.")

            if item.id in vistos:
                raise Exception("O mesmo item foi enviado duas vezes.")
            vistos.add(item.id)

            restante = item.quantidade - ja_devolvido.get(item.id, 0)

            if pedido.quantidade > restante:
                nome = item.produto.nome if item.produto else f"#{item.produto_id}"
                raise Exception(
                    f"{nome}: só restam {formatar_quantidade(restante, item.produto.unidade if item.produto else None)} para devolver."
                )

            valor = (
                Decimal(item.valor_unitario) * pedido.quantidade * fator
            ).quantize(_CENTAVO, rounding=ROUND_HALF_UP)

            devolucao.itens.append(
                ItemDevolucao(
                    item_venda_id=item.id,
                    produto_id=item.produto_id,
                    quantidade=pedido.quantidade,
                    valor=valor,
                )
            )

            total += valor

            produto = db.query(Produto).filter(Produto.id == item.produto_id).first()

            if produto:
                for produto_devolve, quantidade_devolve in _itens_para_baixa_estoque(
                    db, produto, pedido.quantidade
                ):
                    EstoqueLojaRepository.ajustar(
                        db, produto_devolve, venda.loja_id, quantidade_devolve
                    )
                    db.add(produto_devolve)
                    db.add(
                        MovimentoEstoque(
                            produto_id=produto_devolve.id,
                            usuario_id=usuario_id,
                            loja_id=venda.loja_id,
                            tipo="ENTRADA",
                            quantidade=quantidade_devolve,
                            motivo=f"Devolução da venda #{venda.id}",
                        )
                    )

        # arredondamento item a item nunca pode devolver mais do que a
        # venda valeu
        teto = Decimal(venda.valor_total) - valor_devolvido(db, venda.id)
        total = min(total, max(teto, Decimal("0")))

        devolucao.valor_total = total
        db.add(devolucao)

        descricao = f"Devolução da venda #{venda.id}"

        if forma == "PRAZO":

            # abate do caderninho, sem deixar o saldo negativo (mesma
            # regra do cancelamento)
            saldo = MovimentoFiadoRepository.saldo_por_cliente(db, venda.cliente_id)
            abater = min(total, saldo)

            if abater > 0:
                db.add(
                    MovimentoFiado(
                        cliente_id=venda.cliente_id,
                        venda_id=None,
                        usuario_id=usuario_id,
                        tipo="PAGAMENTO",
                        valor=abater,
                        descricao=descricao,
                    )
                )

        if total > 0:

            # mesmo tipo do cancelamento (ESTORNO) pra entrar certinho
            # no fechamento do caixa; só dinheiro mexe na gaveta
            if forma == "DINHEIRO":
                caixa.saldo_final -= total
                db.add(caixa)

            db.add(
                MovimentoCaixa(
                    caixa_id=caixa.id,
                    usuario_id=usuario_id,
                    tipo="ESTORNO",
                    valor=-total,
                    forma_pagamento=forma,
                    descricao=descricao,
                )
            )

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        db.refresh(devolucao)

        NotificacaoService.enviar_para_admins(
            db,
            "Devolução na venda",
            f"Venda #{venda_id} — {moeda(devolucao.valor_total)} devolvido "
            f"({nome_do_usuario(db, usuario_id)})"
            + (f": {devolucao.motivo}" if devolucao.motivo else "."),
        )

        return devolucao
