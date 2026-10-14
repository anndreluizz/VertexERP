from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.conta_pagar import ContaPagar
from app.models.transacao_bancaria import TransacaoBancaria
from app.repositories.transacao_bancaria_repository import (
    TransacaoBancariaRepository,
)
from app.services.ofx_parser import parse_ofx
from app.schemas.transacao_bancaria import (
    TransacaoPreview,
    OfxPreviewResponse,
    CandidatoConciliacao,
)

_JANELA_DIAS = 5


class ExtratoBancarioService:

    @staticmethod
    def pre_visualizar(db: Session, ofx_conteudo: str, loja_id: int | None):

        extrato = parse_ofx(ofx_conteudo)

        fitids = [t.fitid for t in extrato.transacoes]
        existentes = TransacaoBancariaRepository.fitids_existentes(
            db, fitids, loja_id
        )

        previews = [
            TransacaoPreview(
                fitid=t.fitid,
                data=t.data,
                descricao=t.descricao,
                valor=t.valor,
                tipo=t.tipo,
                ja_importada=t.fitid in existentes,
            )
            for t in extrato.transacoes
        ]

        return OfxPreviewResponse(
            banco=extrato.banco,
            conta=extrato.conta,
            transacoes=previews,
            total_novas=sum(1 for p in previews if not p.ja_importada),
            total_ja_importadas=sum(1 for p in previews if p.ja_importada),
        )

    @staticmethod
    def importar(db: Session, ofx_conteudo: str, loja_id: int | None) -> int:

        extrato = parse_ofx(ofx_conteudo)

        fitids = [t.fitid for t in extrato.transacoes]
        existentes = TransacaoBancariaRepository.fitids_existentes(
            db, fitids, loja_id
        )

        novas = [
            TransacaoBancaria(
                loja_id=loja_id,
                fitid=t.fitid,
                data=t.data,
                descricao=t.descricao,
                valor=t.valor,
                tipo=t.tipo,
                status="PENDENTE",
            )
            for t in extrato.transacoes
            if t.fitid not in existentes
        ]

        if novas:
            TransacaoBancariaRepository.criar_lote(db, novas)

        return len(novas)

    @staticmethod
    def listar(
        db: Session, loja_id: int | None = None, status: str | None = None
    ):
        return TransacaoBancariaRepository.listar(db, loja_id, status)

    @staticmethod
    def sugerir_candidatos(db: Session, transacao_id: int):

        transacao = TransacaoBancariaRepository.buscar_por_id(
            db, transacao_id
        )

        if not transacao:
            raise Exception("Transação não encontrada.")

        inicio = transacao.data - timedelta(days=_JANELA_DIAS)
        fim = transacao.data + timedelta(days=_JANELA_DIAS)
        valor_absoluto = abs(transacao.valor)

        candidatos = []

        if transacao.tipo == "DEBITO":

            ja_conciliadas = db.query(TransacaoBancaria.conta_pagar_id).filter(
                TransacaoBancaria.status == "CONCILIADA",
                TransacaoBancaria.conta_pagar_id.is_not(None),
            )

            contas = (
                db.query(ContaPagar)
                .filter(
                    ContaPagar.status == "PAGO",
                    ContaPagar.valor == valor_absoluto,
                    ContaPagar.data_pagamento >= inicio,
                    ContaPagar.data_pagamento <= fim + timedelta(days=1),
                    ContaPagar.id.not_in(ja_conciliadas),
                )
                .all()
            )

            candidatos = [
                CandidatoConciliacao(
                    tipo="PAGAR",
                    id=c.id,
                    descricao=c.descricao or "Despesa",
                    valor=c.valor,
                    data=c.data_pagamento,
                )
                for c in contas
            ]

        # entrada (credito) nao tem com o que conciliar: o que a loja
        # recebe e venda/fiado, que nao vira "conta a receber" (essa
        # tabela antiga foi removida) -- entrada so pode ser ignorada

        return candidatos

    @staticmethod
    def conciliar(
        db: Session,
        transacao_id: int,
        conta_pagar_id: int | None,
        usuario_id: int,
    ):

        transacao = TransacaoBancariaRepository.buscar_por_id(
            db, transacao_id
        )

        if not transacao:
            raise Exception("Transação não encontrada.")

        if transacao.status != "PENDENTE":
            raise Exception("Essa transação já foi conciliada ou ignorada.")

        if not conta_pagar_id:
            raise Exception("Informe a conta a pagar.")

        if transacao.tipo != "DEBITO":
            raise Exception(
                "Só é possível conciliar uma saída (débito) com uma "
                "conta a pagar."
            )

        conta = db.query(ContaPagar).filter(
            ContaPagar.id == conta_pagar_id
        ).first()
        if not conta:
            raise Exception("Conta a pagar não encontrada.")

        # uma conta a pagar so' pode estar linkada a UMA transacao
        # bancaria conciliada por vez -- sem isso, duas linhas de
        # extrato diferentes poderiam "quitar" a mesma despesa
        ja_linkada = (
            db.query(TransacaoBancaria)
            .filter(
                TransacaoBancaria.status == "CONCILIADA",
                TransacaoBancaria.id != transacao_id,
                TransacaoBancaria.conta_pagar_id == conta_pagar_id,
            )
            .first()
        )
        if ja_linkada:
            raise Exception(
                "Essa conta já está conciliada com outra transação "
                "bancária."
            )

        transacao.conta_pagar_id = conta_pagar_id
        transacao.status = "CONCILIADA"
        transacao.conciliado_em = datetime.now()
        transacao.conciliado_por_id = usuario_id

        return TransacaoBancariaRepository.atualizar(db, transacao)

    @staticmethod
    def desconciliar(db: Session, transacao_id: int):

        transacao = TransacaoBancariaRepository.buscar_por_id(
            db, transacao_id
        )

        if not transacao:
            raise Exception("Transação não encontrada.")

        if transacao.status == "PENDENTE":
            raise Exception("Essa transação já está pendente.")

        transacao.conta_pagar_id = None
        transacao.status = "PENDENTE"
        transacao.conciliado_em = None
        transacao.conciliado_por_id = None

        return TransacaoBancariaRepository.atualizar(db, transacao)

    @staticmethod
    def ignorar(db: Session, transacao_id: int):

        transacao = TransacaoBancariaRepository.buscar_por_id(
            db, transacao_id
        )

        if not transacao:
            raise Exception("Transação não encontrada.")

        if transacao.status != "PENDENTE":
            raise Exception("Essa transação já foi conciliada ou ignorada.")

        transacao.status = "IGNORADA"

        return TransacaoBancariaRepository.atualizar(db, transacao)
