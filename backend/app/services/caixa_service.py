from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.enums.status_conta_pagar import StatusContaPagar
from app.models.caixa import Caixa
from app.models.conta_pagar import ContaPagar
from app.models.movimento_caixa import MovimentoCaixa
from app.models.user import User
from app.repositories.caixa_repository import CaixaRepository
from app.schemas.caixa import CaixaCreate
from app.services.notificacao_service import NotificacaoService


class CaixaService:

    @staticmethod
    def abrir(db: Session, dados: CaixaCreate, usuario_id: int, loja_id: int | None = None):

        # trava a linha do usuario ate o commit: duplo clique em "Abrir
        # caixa" (ou dois terminais com o mesmo login) passava as duas
        # requisicoes pela checagem abaixo e criava DOIS caixas abertos.
        # Trava no usuario (e nao indice unico no banco) pra nao arriscar
        # a migracao falhar num banco que ja tenha duplicados.
        db.query(User).filter(User.id == usuario_id).with_for_update().first()

        caixa = CaixaRepository.buscar_aberto(db, usuario_id, loja_id)

        if caixa:
            raise Exception("Você já tem um caixa aberto.")

        novo = Caixa(
            saldo_inicial=dados.saldo_inicial,
            saldo_final=dados.saldo_inicial,
            status="ABERTO",
            usuario_id=usuario_id,
            loja_id=loja_id,
        )

        novo = CaixaRepository.criar(db, novo)

        operador = db.query(User).filter(User.id == usuario_id).first()

        NotificacaoService.enviar_para_admins(
            db,
            "Caixa aberto",
            f"{operador.nome if operador else 'Um operador'} abriu um "
            f"caixa com R$ {dados.saldo_inicial:.2f} de troco inicial.",
            excluir_usuario_id=usuario_id,
        )

        return novo

    @staticmethod
    def fechar(
        db: Session,
        usuario_id: int,
        valor_contado: Decimal | None = None,
        observacoes: str | None = None,
        loja_id: int | None = None,
    ):

        caixa = CaixaRepository.buscar_aberto(
            db, usuario_id, loja_id, para_atualizar=True
        )

        if not caixa:
            raise Exception("Nenhum caixa aberto.")

        caixa.status = "FECHADO"
        caixa.data_fechamento = datetime.now()
        caixa.valor_contado = valor_contado
        caixa.observacoes = observacoes

        caixa = CaixaRepository.atualizar(db, caixa)

        operador = db.query(User).filter(User.id == usuario_id).first()

        NotificacaoService.enviar_para_admins(
            db,
            "Caixa fechado",
            f"{operador.nome if operador else 'Um operador'} fechou o "
            f"caixa com R$ {caixa.saldo_final:.2f} em caixa.",
            excluir_usuario_id=usuario_id,
        )

        return caixa

    @staticmethod
    def caixa_aberto(db: Session, usuario_id: int, loja_id: int | None = None):
        return CaixaRepository.buscar_aberto(db, usuario_id, loja_id)

    @staticmethod
    def historico(db: Session, limite: int = 20, loja_id: int | None = None):
        return CaixaRepository.listar(db, limite, loja_id)

    @staticmethod
    def entradas(
        db: Session,
        inicio: date | None,
        fim: date | None,
        loja_id: int | None = None,
    ) -> dict:
        """Dinheiro que entrou de verdade no periodo, somando todos os
        caixas: vendas (menos estornos) e fiado recebido, por forma de
        pagamento. Troco inicial, suprimento e sangria ficam de fora --
        so mudam dinheiro de lugar (somar o total de cada turno contaria
        o mesmo troco varias vezes). Venda a prazo tambem: nao entrou.
        sobrou = entrou - contas a pagar pagas - sangrias."""

        query = (
            db.query(
                MovimentoCaixa.tipo,
                MovimentoCaixa.forma_pagamento,
                func.coalesce(func.sum(MovimentoCaixa.valor), 0),
            )
            .join(Caixa, Caixa.id == MovimentoCaixa.caixa_id)
            .filter(MovimentoCaixa.tipo.in_(
                ("VENDA", "ESTORNO", "RECEBIMENTO_FIADO", "SANGRIA")
            ))
            .group_by(MovimentoCaixa.tipo, MovimentoCaixa.forma_pagamento)
        )
        if inicio:
            query = query.filter(MovimentoCaixa.data >= inicio)
        if fim:
            query = query.filter(MovimentoCaixa.data < fim + timedelta(days=1))
        if loja_id is not None:
            query = query.filter(Caixa.loja_id == loja_id)

        zero = Decimal("0")
        por_forma = {"dinheiro": zero, "pix": zero, "cartao": zero, "outros": zero}
        fiado_recebido = sangrias = vendas_prazo = zero
        # venda grava DEBITO/CREDITO; recebimento de fiado no cartao grava CARTAO
        chave = {
            "DINHEIRO": "dinheiro", "PIX": "pix",
            "DEBITO": "cartao", "CREDITO": "cartao", "CARTAO": "cartao",
        }

        for tipo, forma, valor in query.all():
            if tipo == "SANGRIA":
                sangrias += valor
                continue
            if forma == "PRAZO":
                vendas_prazo += valor
                continue
            por_forma[chave.get(forma, "outros")] += valor
            if tipo == "RECEBIMENTO_FIADO":
                fiado_recebido += valor

        # contas a pagar pagas no periodo (qualquer forma). A paga em
        # dinheiro tambem vira movimento PAGAMENTO no caixa, mas esse
        # tipo nao entra na soma acima -- entao nao conta duas vezes
        contas = (
            db.query(func.coalesce(func.sum(ContaPagar.valor), 0))
            .filter(ContaPagar.status == StatusContaPagar.PAGO.value)
        )
        if inicio:
            contas = contas.filter(ContaPagar.data_pagamento >= inicio)
        if fim:
            contas = contas.filter(ContaPagar.data_pagamento < fim + timedelta(days=1))
        if loja_id is not None:
            contas = contas.filter(ContaPagar.loja_id == loja_id)
        contas_pagas = contas.scalar() or zero

        total = sum(por_forma.values(), zero)
        return {
            **por_forma,
            "fiado_recebido": fiado_recebido,
            "total": total,
            "sangrias": sangrias,
            "vendas_prazo": vendas_prazo,
            "contas_pagas": contas_pagas,
            "sobrou": total - contas_pagas - sangrias,
        }

    @staticmethod
    def resumo(db: Session, caixa: Caixa) -> dict:

        def soma(tipo=None, forma_pagamento=None):

            query = db.query(
                func.coalesce(func.sum(MovimentoCaixa.valor), 0)
            ).filter(
                MovimentoCaixa.caixa_id == caixa.id
            )

            if tipo:
                query = query.filter(MovimentoCaixa.tipo == tipo)

            if forma_pagamento:
                query = query.filter(
                    MovimentoCaixa.forma_pagamento == forma_pagamento
                )

            return query.scalar() or Decimal("0")

        def soma_vendas(forma_pagamento):
            # Soma VENDA + ESTORNO daquela forma de pagamento -- o
            # ESTORNO ja fica gravado com valor negativo (ver
            # VendaService.excluir), entao e soma direta. Sem isso,
            # cancelar uma venda pix/cartao/prazo nao descontava o
            # total aqui (so dinheiro mexia em saldo_final).
            return soma(
                tipo="VENDA", forma_pagamento=forma_pagamento
            ) + soma(tipo="ESTORNO", forma_pagamento=forma_pagamento)

        vendas_dinheiro = soma_vendas("DINHEIRO")
        vendas_pix = soma_vendas("PIX")
        vendas_debito = soma_vendas("DEBITO")
        vendas_credito = soma_vendas("CREDITO")
        vendas_prazo = soma_vendas("PRAZO")
        suprimentos = soma(tipo="SUPRIMENTO")
        sangrias = soma(tipo="SANGRIA")

        recebimentos_fiado = soma(tipo="RECEBIMENTO_FIADO")
        recebimentos_fiado_dinheiro = soma(
            tipo="RECEBIMENTO_FIADO", forma_pagamento="DINHEIRO"
        )

        # saldo_final ja e mantido incrementalmente (troco inicial +
        # vendas em dinheiro + suprimentos - sangrias - estornos +
        # recebimentos de fiado em dinheiro), entao ele *e* o total
        # previsto em especie na gaveta
        total_previsto = caixa.saldo_final

        vendas_cartao = vendas_debito + vendas_credito

        # a parte do recebimento de fiado em dinheiro ja esta dentro
        # de total_previsto (via saldo_final); so a parte via pix/
        # cartao precisa ser somada aqui pra nao ficar de fora
        recebimentos_fiado_outros = (
            recebimentos_fiado - recebimentos_fiado_dinheiro
        )

        total_geral = (
            total_previsto
            + vendas_pix
            + vendas_cartao
            + recebimentos_fiado_outros
        )

        return {
            "saldo_inicial": caixa.saldo_inicial,
            "vendas_dinheiro": vendas_dinheiro,
            "vendas_pix": vendas_pix,
            "vendas_cartao": vendas_cartao,
            "vendas_prazo": vendas_prazo,
            "suprimentos": suprimentos,
            "sangrias": sangrias,
            "recebimentos_fiado": recebimentos_fiado,
            "total_previsto": total_previsto,
            "total_geral": total_geral,
        }

    @staticmethod
    def resumo_aberto(db: Session, usuario_id: int, loja_id: int | None = None):

        caixa = CaixaRepository.buscar_aberto(db, usuario_id, loja_id)

        if not caixa:
            return None

        return CaixaService.resumo(db, caixa)
