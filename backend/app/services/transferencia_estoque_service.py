from sqlalchemy.orm import Session

from app.repositories.produto_repository import ProdutoRepository
from app.repositories.transferencia_estoque_repository import (
    TransferenciaEstoqueRepository,
)
from app.models.transferencia_estoque import TransferenciaEstoque
from app.schemas.movimento_estoque import MovimentoEstoqueCreate
from app.schemas.transferencia_estoque import TransferenciaEstoqueCreate
from app.services.movimento_estoque_service import MovimentoEstoqueService


class TransferenciaEstoqueService:

    @staticmethod
    def criar(
        db: Session,
        dados: TransferenciaEstoqueCreate,
        usuario_id: int,
        loja_origem_id: int,
    ):
        if loja_origem_id is None:
            raise Exception(
                "Não foi possível determinar a loja de origem da transferência."
            )

        if loja_origem_id == dados.loja_destino_id:
            raise Exception(
                "Loja de origem e destino não podem ser a mesma."
            )

        produto = ProdutoRepository.buscar_por_id(db, dados.produto_id)

        if not produto:
            raise Exception(f"Produto {dados.produto_id} não encontrado.")

        # exclusivo de uma loja: a destino nao enxerga o produto e o
        # estoque transferido sumiria
        if produto.loja_id is not None:
            raise Exception(
                f'O produto "{produto.nome}" é exclusivo de uma loja e não '
                "pode ser transferido. Troque o código dele para liberar."
            )

        transferencia = TransferenciaEstoque(
            produto_id=dados.produto_id,
            loja_origem_id=loja_origem_id,
            loja_destino_id=dados.loja_destino_id,
            quantidade=dados.quantidade,
            usuario_id=usuario_id,
            motivo=dados.motivo,
        )

        TransferenciaEstoqueRepository.criar(db, transferencia)

        motivo_movimento = (
            f"Transferência #{transferencia.id}"
            + (f" — {dados.motivo}" if dados.motivo else "")
        )

        # SAIDA primeiro: se o estoque da origem for insuficiente,
        # MovimentoEstoqueService.criar levanta ANTES de tocar o banco --
        # nada fica gravado (nem essa transferencia, que so' foi
        # flush()ada, nao commitada).
        MovimentoEstoqueService.criar(
            db,
            MovimentoEstoqueCreate(
                produto_id=dados.produto_id,
                tipo="SAIDA",
                quantidade=dados.quantidade,
                motivo=motivo_movimento,
            ),
            usuario_id,
            loja_origem_id,
            transferencia.id,
        )

        MovimentoEstoqueService.criar(
            db,
            MovimentoEstoqueCreate(
                produto_id=dados.produto_id,
                tipo="ENTRADA",
                quantidade=dados.quantidade,
                motivo=motivo_movimento,
            ),
            usuario_id,
            dados.loja_destino_id,
            transferencia.id,
        )

        return transferencia

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return TransferenciaEstoqueRepository.listar(db, skip, limit)
