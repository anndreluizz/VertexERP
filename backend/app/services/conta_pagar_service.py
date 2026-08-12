from datetime import datetime

from sqlalchemy.orm import Session

from app.enums.status_conta_pagar import StatusContaPagar

from app.models.compra import Compra
from app.models.conta_pagar import ContaPagar

from app.repositories.conta_pagar_repository import (
    ContaPagarRepository,
)

from app.schemas.conta_pagar import (
    ContaPagarCreate,
    ContaPagarUpdate,
)

from app.services.caixa_operacao_service import (
    CaixaOperacaoService,
)


class ContaPagarService:

    @staticmethod
    def criar(
        db: Session,
        dados: ContaPagarCreate,
    ):

        conta = ContaPagar(
            fornecedor_id=dados.fornecedor_id,
            compra_id=dados.compra_id,
            data_emissao=datetime.utcnow(),
            data_vencimento=dados.data_vencimento,
            data_pagamento=None,
            valor=float(dados.valor),
            observacao=dados.observacao,
            numero_boleto=dados.numero_boleto,
            status=StatusContaPagar.PENDENTE.value,
        )

        return ContaPagarRepository.criar(
            db,
            conta,
        )

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return ContaPagarRepository.listar(db, skip, limit)

    @staticmethod
    def listar_pendentes(db: Session):
        return ContaPagarRepository.listar_pendentes(db)

    @staticmethod
    def listar_pagas(db: Session, skip: int = 0, limit: int = 100):
        return ContaPagarRepository.listar_pagas(db, skip, limit)

    @staticmethod
    def buscar_por_id(
        db: Session,
        conta_id: int,
    ):
        return ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

    @staticmethod
    def atualizar(
        db: Session,
        conta_id: int,
        dados: ContaPagarUpdate,
    ):

        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        dados_dict = dados.dict(
            exclude_unset=True
        )

        for campo, valor in dados_dict.items():
            setattr(conta, campo, valor)

        return ContaPagarRepository.atualizar(
            db,
            conta,
        )

    @staticmethod
    def pagar(
        db: Session,
        conta_id: int,
        usuario_id: int,
    ):

        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        if conta.status == StatusContaPagar.PAGO.value:
            raise Exception("Conta já foi paga.")

        if conta.status == StatusContaPagar.CANCELADO.value:
            raise Exception("Conta cancelada.")

        caixa = CaixaOperacaoService.buscar_caixa_aberto(
            db
        )

        if not caixa:
            raise Exception("Nenhum caixa aberto.")

        conta.status = StatusContaPagar.PAGO.value
        conta.data_pagamento = datetime.utcnow()

        conta = ContaPagarRepository.atualizar(
            db,
            conta,
        )

        CaixaOperacaoService.registrar_movimento(
            db=db,
            caixa=caixa,
            usuario_id=usuario_id,
            tipo="PAGAMENTO",
            descricao=f"Pagamento Conta Nº {conta.id}",
            valor=-float(conta.valor),
        )

        return conta

    @staticmethod
    def cancelar(
        db: Session,
        conta_id: int,
    ):

        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        if conta.status == StatusContaPagar.PAGO.value:
            raise Exception(
                "Não é possível cancelar uma conta paga."
            )

        conta.status = StatusContaPagar.CANCELADO.value

        return ContaPagarRepository.atualizar(
            db,
            conta,
        )

    @staticmethod
    def criar_compra_prazo(
        db: Session,
        compra: Compra,
    ):

        if compra.fornecedor_id is None:
            raise Exception(
                "Compra a prazo exige um fornecedor."
            )

        if compra.data_vencimento is None:
            raise Exception(
                "Informe a data de vencimento."
            )

        conta = ContaPagar(
            fornecedor_id=compra.fornecedor_id,
            compra_id=compra.id,
            data_emissao=datetime.utcnow(),
            data_vencimento=compra.data_vencimento,
            data_pagamento=None,
            valor=compra.valor_total,
            observacao="Gerada automaticamente pela compra.",
            status=StatusContaPagar.PENDENTE.value,
        )

        return ContaPagarRepository.criar(
            db,
            conta,
        )