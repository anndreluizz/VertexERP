from sqlalchemy.orm import Session

from app.models.movimento_fiado import MovimentoFiado
from app.models.movimento_caixa import MovimentoCaixa
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.caixa_repository import CaixaRepository
from app.repositories.movimento_fiado_repository import (
    MovimentoFiadoRepository,
)
from app.schemas.movimento_fiado import MovimentoFiadoCreate


class MovimentoFiadoService:

    @staticmethod
    def criar(
        db: Session,
        dados: MovimentoFiadoCreate,
        usuario_id: int,
    ):

        cliente = ClienteRepository.buscar_por_id(db, dados.cliente_id)

        if not cliente:
            raise Exception("Cliente não encontrado.")

        tipo = dados.tipo.upper()

        if tipo not in ("COMPRA", "PAGAMENTO"):
            raise Exception("Tipo de movimento inválido.")

        if tipo == "PAGAMENTO":

            saldo_atual = MovimentoFiadoRepository.saldo_por_cliente(
                db,
                dados.cliente_id,
            )

            if dados.valor > saldo_atual:
                raise Exception(
                    f"O valor do pagamento (R$ {dados.valor:.2f}) é "
                    f"maior que o saldo devedor do cliente "
                    f"(R$ {saldo_atual:.2f})."
                )

        forma_pagamento = (
            dados.forma_pagamento.upper()
            if dados.forma_pagamento
            else None
        )

        # so registra no caixa quando for um pagamento de verdade
        # (recebido no balcao); ajustes internos do sistema (ex.:
        # estorno de venda fiado) nao informam forma_pagamento
        if tipo == "PAGAMENTO" and forma_pagamento:

            caixa = CaixaRepository.buscar_aberto(db)

            if not caixa:
                raise Exception(
                    "Não existe caixa aberto. Abra o caixa antes de "
                    "registrar o recebimento."
                )

            if forma_pagamento == "DINHEIRO":
                caixa.saldo_final += dados.valor
                db.add(caixa)

            db.add(
                MovimentoCaixa(
                    caixa_id=caixa.id,
                    usuario_id=usuario_id,
                    tipo="RECEBIMENTO_FIADO",
                    valor=dados.valor,
                    forma_pagamento=forma_pagamento,
                    descricao=f"Pagamento fiado - {cliente.nome}",
                )
            )

        movimento = MovimentoFiado(
            cliente_id=dados.cliente_id,
            venda_id=dados.venda_id,
            usuario_id=usuario_id,
            tipo=tipo,
            valor=dados.valor,
            descricao=dados.descricao,
            forma_pagamento=forma_pagamento,
        )

        return MovimentoFiadoRepository.criar(db, movimento)

    @staticmethod
    def criar_compra_da_venda(db: Session, venda, usuario_id: int):

        movimento = MovimentoFiado(
            cliente_id=venda.cliente_id,
            venda_id=venda.id,
            usuario_id=usuario_id,
            tipo="COMPRA",
            valor=venda.valor_total,
            descricao=f"Venda #{venda.id}",
        )

        db.add(movimento)

        return movimento

    @staticmethod
    def listar(db: Session):
        return MovimentoFiadoRepository.listar(db)

    @staticmethod
    def listar_por_cliente(db: Session, cliente_id: int):
        return MovimentoFiadoRepository.listar_por_cliente(
            db,
            cliente_id,
        )

    @staticmethod
    def saldo_por_cliente(db: Session, cliente_id: int):
        return MovimentoFiadoRepository.saldo_por_cliente(
            db,
            cliente_id,
        )
