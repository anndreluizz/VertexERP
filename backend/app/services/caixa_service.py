from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.caixa import Caixa
from app.models.movimento_caixa import MovimentoCaixa
from app.models.user import User
from app.repositories.caixa_repository import CaixaRepository
from app.schemas.caixa import CaixaCreate
from app.services.notificacao_service import NotificacaoService


class CaixaService:

    @staticmethod
    def abrir(db: Session, dados: CaixaCreate, usuario_id: int, loja_id: int | None = None):

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

        caixa = CaixaRepository.buscar_aberto(db, usuario_id, loja_id)

        if not caixa:
            raise Exception("Nenhum caixa aberto.")

        caixa.status = "FECHADO"
        caixa.data_fechamento = datetime.utcnow()
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
    def historico(db: Session, limite: int = 20):
        return CaixaRepository.listar(db, limite)

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

        vendas_dinheiro = soma(
            tipo="VENDA", forma_pagamento="DINHEIRO"
        )
        vendas_pix = soma(tipo="VENDA", forma_pagamento="PIX")
        vendas_debito = soma(tipo="VENDA", forma_pagamento="DEBITO")
        vendas_credito = soma(
            tipo="VENDA", forma_pagamento="CREDITO"
        )
        vendas_prazo = soma(tipo="VENDA", forma_pagamento="PRAZO")
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
