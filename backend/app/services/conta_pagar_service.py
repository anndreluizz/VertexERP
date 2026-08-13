import base64
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

from app.services.conta_pagar_evento_service import ContaPagarEventoService
from app.services.notificacao_service import NotificacaoService

# rotulos legiveis pra montar o "detalhes" dos eventos de auditoria --
# mesmos valores usados em Venda.forma_pagamento.
_NOMES_FORMA_PAGAMENTO = {
    "PIX": "Pix",
    "TRANSFERENCIA": "Transferência",
    "DINHEIRO": "Dinheiro",
    "CARTAO": "Cartão",
    "BOLETO": "Boleto",
}


def _moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "_").replace(".", ",").replace(
        "_", "."
    )


class ContaPagarService:

    @staticmethod
    def criar(
        db: Session,
        dados: ContaPagarCreate,
        usuario_id: int | None = None,
        dispositivo: str | None = None,
    ):

        conta = ContaPagar(
            fornecedor_id=dados.fornecedor_id,
            compra_id=dados.compra_id,
            data_emissao=datetime.utcnow(),
            data_vencimento=dados.data_vencimento,
            data_pagamento=None,
            valor=dados.valor,
            descricao=dados.descricao,
            categoria=dados.categoria,
            observacao=dados.observacao,
            numero_boleto=dados.numero_boleto,
            status=StatusContaPagar.PENDENTE.value,
        )

        if dados.documento_base64:
            conta.documento = base64.b64decode(dados.documento_base64)
            conta.documento_nome = dados.documento_nome
            conta.documento_tipo = dados.documento_tipo

        conta = ContaPagarRepository.criar(
            db,
            conta,
        )

        ContaPagarEventoService.registrar(
            db, conta.id, "CRIADA",
            usuario_id=usuario_id, dispositivo=dispositivo,
        )

        if dados.documento_base64:
            ContaPagarEventoService.registrar(
                db, conta.id, "DOCUMENTO_ANEXADO",
                usuario_id=usuario_id, dispositivo=dispositivo,
            )
            NotificacaoService.enviar_para_admins(
                db,
                "Novo boleto cadastrado",
                f"{conta.descricao or 'Despesa'} — {_moeda(conta.valor)}",
                excluir_usuario_id=usuario_id,
            )

        return conta

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
        usuario_id: int | None = None,
        dispositivo: str | None = None,
    ):

        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        dados_dict = dados.dict(
            exclude_unset=True,
            exclude={
                "documento_base64",
                "documento_nome",
                "documento_tipo",
            },
        )

        for campo, valor in dados_dict.items():
            setattr(conta, campo, valor)

        # so troca o documento se vier um novo -- editar outros campos
        # da despesa nao pode apagar o boleto ja anexado sem querer.
        if dados.documento_base64:
            conta.documento = base64.b64decode(dados.documento_base64)
            conta.documento_nome = dados.documento_nome
            conta.documento_tipo = dados.documento_tipo

        conta = ContaPagarRepository.atualizar(
            db,
            conta,
        )

        if dados.documento_base64:
            ContaPagarEventoService.registrar(
                db, conta.id, "DOCUMENTO_ANEXADO",
                usuario_id=usuario_id, dispositivo=dispositivo,
            )
            NotificacaoService.enviar_para_admins(
                db,
                "Novo boleto cadastrado",
                f"{conta.descricao or 'Despesa'} — {_moeda(conta.valor)}",
                excluir_usuario_id=usuario_id,
            )

        return conta

    @staticmethod
    def remover_documento(
        db: Session,
        conta_id: int,
    ):

        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        conta.documento = None
        conta.documento_nome = None
        conta.documento_tipo = None

        return ContaPagarRepository.atualizar(
            db,
            conta,
        )

    @staticmethod
    def pagar(
        db: Session,
        conta_id: int,
        forma_pagamento: str | None = None,
        banco_pagamento: str | None = None,
        numero_transacao: str | None = None,
        comprovante_base64: str | None = None,
        comprovante_nome: str | None = None,
        comprovante_tipo: str | None = None,
        usuario_id: int | None = None,
        dispositivo: str | None = None,
    ):
        # Despesas do estabelecimento (aluguel, funcionaria, contas)
        # normalmente sao pagas via transferencia/PIX da conta da loja,
        # nao saem da gaveta do caixa fisico do PDV — por isso marcar
        # como paga aqui nao mexe no caixa, diferente de uma venda.

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

        conta.status = StatusContaPagar.PAGO.value
        conta.data_pagamento = datetime.utcnow()
        conta.forma_pagamento = forma_pagamento
        conta.banco_pagamento = banco_pagamento
        conta.numero_transacao = numero_transacao

        if comprovante_base64:
            conta.comprovante_pagamento = base64.b64decode(
                comprovante_base64
            )
            conta.comprovante_pagamento_nome = comprovante_nome
            conta.comprovante_pagamento_tipo = comprovante_tipo

        conta = ContaPagarRepository.atualizar(
            db,
            conta,
        )

        detalhes = None
        if forma_pagamento:
            detalhes = f"Pago via {_NOMES_FORMA_PAGAMENTO.get(forma_pagamento, forma_pagamento)}."

        ContaPagarEventoService.registrar(
            db, conta.id, "PAGA",
            usuario_id=usuario_id, dispositivo=dispositivo,
            detalhes=detalhes,
        )

        NotificacaoService.enviar_para_admins(
            db,
            "Pagamento realizado",
            f"{conta.descricao or 'Despesa'} — {_moeda(conta.valor)}",
            excluir_usuario_id=usuario_id,
        )

        if comprovante_base64:
            ContaPagarEventoService.registrar(
                db, conta.id, "COMPROVANTE_ANEXADO",
                usuario_id=usuario_id, dispositivo=dispositivo,
            )
            NotificacaoService.enviar_para_admins(
                db,
                "Comprovante enviado",
                f"{conta.descricao or 'Despesa'} — {_moeda(conta.valor)}",
                excluir_usuario_id=usuario_id,
            )

        return conta

    @staticmethod
    def trocar_comprovante(
        db: Session,
        conta_id: int,
        comprovante_base64: str,
        comprovante_nome: str | None = None,
        comprovante_tipo: str | None = None,
        usuario_id: int | None = None,
        dispositivo: str | None = None,
    ):
        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        if conta.status != StatusContaPagar.PAGO.value:
            raise Exception(
                "Só é possível trocar o comprovante de uma conta já paga."
            )

        conta.comprovante_pagamento = base64.b64decode(comprovante_base64)
        conta.comprovante_pagamento_nome = comprovante_nome
        conta.comprovante_pagamento_tipo = comprovante_tipo

        conta = ContaPagarRepository.atualizar(
            db,
            conta,
        )

        ContaPagarEventoService.registrar(
            db, conta.id, "COMPROVANTE_TROCADO",
            usuario_id=usuario_id, dispositivo=dispositivo,
        )

        NotificacaoService.enviar_para_admins(
            db,
            "Comprovante enviado",
            f"{conta.descricao or 'Despesa'} — {_moeda(conta.valor)}",
            excluir_usuario_id=usuario_id,
        )

        return conta

    @staticmethod
    def cancelar(
        db: Session,
        conta_id: int,
        usuario_id: int | None = None,
        dispositivo: str | None = None,
    ):
        """Cancela uma despesa (pendente ou ja paga) -- diferente de
        excluir(), o registro continua existindo com status CANCELADO,
        preservando o historico. Quem decide se isso pode rodar direto
        ou precisa de aprovacao e a camada de API (ver
        api/v1/contas_pagar.py e app/services/aprovacao_service.py)."""

        conta = ContaPagarRepository.buscar_por_id(
            db,
            conta_id,
        )

        if not conta:
            raise Exception("Conta não encontrada.")

        if conta.status == StatusContaPagar.CANCELADO.value:
            raise Exception("Conta já está cancelada.")

        conta.status = StatusContaPagar.CANCELADO.value

        conta = ContaPagarRepository.atualizar(
            db,
            conta,
        )

        ContaPagarEventoService.registrar(
            db, conta.id, "CANCELADA",
            usuario_id=usuario_id, dispositivo=dispositivo,
        )

        return conta

    @staticmethod
    def excluir(
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
                "Não é possível excluir uma despesa já paga. "
                "Use cancelar em vez de excluir."
            )

        ContaPagarRepository.excluir(db, conta)

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

        conta = ContaPagarRepository.criar(
            db,
            conta,
        )

        ContaPagarEventoService.registrar(db, conta.id, "CRIADA")

        return conta
