from datetime import datetime

from sqlalchemy.orm import Session

from app.enums.status_conta_receber import StatusContaReceber
from app.models.conta_receber import ContaReceber
from app.models.venda import Venda

from app.repositories.cliente_repository import ClienteRepository
from app.repositories.conta_receber_repository import (
    ContaReceberRepository,
)

from app.schemas.conta_receber import (
    ContaReceberCreate,
    ContaReceberUpdate,
)

from app.services.caixa_operacao_service import CaixaOperacaoService


class ContaReceberService:

    @staticmethod
    def criar(
        db: Session,
        dados: ContaReceberCreate,
        loja_id: int | None = None,
    ):

        cliente = ClienteRepository.buscar_por_id(
            db,
            dados.cliente_id,
        )

        if not cliente:
            raise Exception("Cliente não encontrado.")

        conta = ContaReceber(
            cliente_id=dados.cliente_id,
            venda_id=dados.venda_id,
            data_emissao=datetime.utcnow(),
            data_vencimento=dados.data_vencimento,
            data_recebimento=None,
            valor=dados.valor,
            observacao=dados.observacao,
            status=StatusContaReceber.PENDENTE.value,
            loja_id=loja_id,
        )

        return ContaReceberRepository.criar(
            db,
            conta,
        )

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100, loja_id: int | None = None):
        return ContaReceberRepository.listar(db, skip, limit, loja_id)

    @staticmethod
    def listar_pendentes(db: Session):
        return ContaReceberRepository.listar_pendentes(db)

    @staticmethod
    def listar_recebidas(db: Session, skip: int = 0, limit: int = 100):
        return ContaReceberRepository.listar_recebidas(db, skip, limit)

    @staticmethod
    def listar_por_cliente(
        db: Session,
        cliente_id: int,
        skip: int = 0,
        limit: int = 100,
    ):
        return ContaReceberRepository.listar_por_cliente(
            db,
            cliente_id,
            skip,
            limit,
        )

    @staticmethod
    def buscar_por_id(
        db: Session,
        conta_id: int,
    ):
        return ContaReceberRepository.buscar_por_id(
            db,
            conta_id,
        )

    @staticmethod
    def receber(
        db: Session,
        conta_id: int,
        usuario_id: int,
    ):

        conta = ContaReceberRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        if conta.status == StatusContaReceber.RECEBIDO.value:
            raise Exception("Conta já foi recebida.")

        if conta.status == StatusContaReceber.CANCELADO.value:
            raise Exception("Conta cancelada não pode ser recebida.")

        # confere ANTES de mudar qualquer coisa -- se checasse só depois
        # de marcar RECEBIDO e commitar (como estava antes), uma
        # tentativa sem caixa aberto deixava a conta marcada como
        # recebida com o recebimento nunca tendo sido registrado em
        # lugar nenhum (mesmo criterio já usado em ContaPagarService.pagar()).
        caixa = CaixaOperacaoService.buscar_caixa_aberto(db, usuario_id)

        if not caixa:
            raise Exception("Nenhum caixa aberto.")

        conta.status = StatusContaReceber.RECEBIDO.value
        conta.data_recebimento = datetime.utcnow()

        conta = ContaReceberRepository.atualizar(
            db,
            conta,
        )

        CaixaOperacaoService.registrar_movimento(
            db=db,
            caixa=caixa,
            usuario_id=usuario_id,
            tipo="RECEBIMENTO",
            descricao=f"Recebimento da Conta Nº {conta.id}",
            valor=conta.valor,
        )

        return conta

    @staticmethod
    def cancelar(
        db: Session,
        conta_id: int,
    ):

        conta = ContaReceberRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        if conta.status == StatusContaReceber.RECEBIDO.value:
            raise Exception(
                "Não é possível cancelar uma conta já recebida."
            )

        conta.status = StatusContaReceber.CANCELADO.value

        return ContaReceberRepository.atualizar(
            db,
            conta,
        )

    @staticmethod
    def atualizar(
        db: Session,
        conta_id: int,
        dados: ContaReceberUpdate,
    ):

        conta = ContaReceberRepository.buscar_por_id(
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

        return ContaReceberRepository.atualizar(
            db,
            conta,
        )

    @staticmethod
    def criar_venda_prazo(
        db: Session,
        venda: Venda,
    ):

        if venda.cliente_id is None:
            raise Exception(
                "Venda a prazo exige um cliente."
            )

        if venda.data_vencimento is None:
            raise Exception(
                "Informe a data de vencimento."
            )

        conta = ContaReceber(
            cliente_id=venda.cliente_id,
            venda_id=venda.id,
            data_emissao=datetime.utcnow(),
            data_vencimento=venda.data_vencimento,
            data_recebimento=None,
            valor=venda.valor_total,
            observacao="Gerada automaticamente pela venda.",
            status=StatusContaReceber.PENDENTE.value,
            loja_id=venda.loja_id,
        )

        return ContaReceberRepository.criar(
            db,
            conta,
        )