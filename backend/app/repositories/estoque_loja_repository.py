from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.estoque_loja import EstoqueLoja
from app.models.produto import Produto


class EstoqueLojaRepository:

    @staticmethod
    def obter_ou_criar(db: Session, produto_id: int, loja_id: int):
        # sempre comeca em 0 -- NUNCA herda produto.estoque aqui. Se
        # herdasse, a primeira loja nova que tocasse num produto
        # "roubaria" uma copia fantasma do estoque que fisicamente so
        # existe na Matriz (que ja foi semeada por uma migracao de
        # dados especifica, ver 7596e4010a1f -> proxima migration).
        registro = (
            db.query(EstoqueLoja)
            .filter(
                EstoqueLoja.produto_id == produto_id,
                EstoqueLoja.loja_id == loja_id,
            )
            .first()
        )

        if registro is None:
            registro = EstoqueLoja(
                produto_id=produto_id,
                loja_id=loja_id,
                quantidade=0,
                estoque_minimo=0,
            )
            db.add(registro)
            db.flush()

        return registro

    @staticmethod
    def ajustar(db: Session, produto: Produto, loja_id: int | None, delta: int):
        """Aplica delta (positivo ou negativo) na quantidade da loja e
        recalcula produto.estoque como a soma entre todas as lojas --
        mantem esse campo util pra quem ainda le o agregado (PDV,
        dashboard) sem precisar saber de loja nenhuma.

        loja_id=None (fallback de resolver_loja_id quando nao existe
        loja nenhuma cadastrada ainda, ex.: banco de teste) cai no
        comportamento antigo -- mexe direto em produto.estoque, sem
        EstoqueLoja nenhum envolvido."""

        if loja_id is None:
            produto.estoque += delta
            return

        registro = EstoqueLojaRepository.obter_ou_criar(
            db, produto.id, loja_id
        )
        registro.quantidade += delta
        db.add(registro)

        produto.estoque = (
            db.query(func.coalesce(func.sum(EstoqueLoja.quantidade), 0))
            .filter(EstoqueLoja.produto_id == produto.id)
            .scalar()
        )
