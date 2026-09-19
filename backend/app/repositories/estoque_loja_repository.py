from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.estoque_loja import EstoqueLoja
from app.models.produto import Produto


class EstoqueLojaRepository:

    @staticmethod
    def obter_ou_criar(db: Session, produto_id: int, loja_id: int):
        # quantidade sempre comeca em 0 -- NUNCA herda produto.estoque
        # aqui. Se herdasse, a primeira loja nova que tocasse num
        # produto "roubaria" uma copia fantasma do estoque que
        # fisicamente so existe na Matriz (que ja foi semeada por uma
        # migracao de dados especifica, ver 7596e4010a1f -> proxima
        # migration).
        registro = (
            db.query(EstoqueLoja)
            .filter(
                EstoqueLoja.produto_id == produto_id,
                EstoqueLoja.loja_id == loja_id,
            )
            .first()
        )

        if registro is None:
            # estoque_minimo, diferente de quantidade, e' uma
            # CONFIGURACAO (nao uma quantidade fisica real) -- copiar o
            # minimo global do produto como ponto de partida da loja
            # nova e' um default razoavel, nao um "roubo" de estoque.
            # Sem isso, toda loja nova comecaria com minimo 0 e o
            # alerta de estoque baixo ficaria desligado ate alguem
            # configurar na mao.
            minimo_padrao = (
                db.query(Produto.estoque_minimo)
                .filter(Produto.id == produto_id)
                .scalar()
            ) or 0

            registro = EstoqueLoja(
                produto_id=produto_id,
                loja_id=loja_id,
                quantidade=0,
                estoque_minimo=minimo_padrao,
            )
            db.add(registro)
            db.flush()

        return registro

    @staticmethod
    def minimos_por_loja(
        db: Session, produto_ids: list[int], loja_id: int
    ) -> dict[int, int]:
        """Estoque minimo configurado de cada produto NESSA loja
        especifica. Produto sem linha em EstoqueLoja ainda (nunca foi
        tocado nessa loja) fica de fora do dict -- quem chama deve
        cair pro minimo GLOBAL (Produto.estoque_minimo) como fallback,
        nao pra 0, senao "nunca configurou" vira "nunca alerta"."""

        if not produto_ids:
            return {}

        linhas = (
            db.query(EstoqueLoja.produto_id, EstoqueLoja.estoque_minimo)
            .filter(
                EstoqueLoja.produto_id.in_(produto_ids),
                EstoqueLoja.loja_id == loja_id,
            )
            .all()
        )

        return {produto_id: minimo for produto_id, minimo in linhas}

    @staticmethod
    def quantidades_por_loja(
        db: Session, produto_ids: list[int], loja_id: int
    ) -> dict[int, int]:
        """Quantidade fisica de cada produto NESSA loja especifica --
        usado pra sobrescrever Produto.estoque (soma agregada entre
        lojas) quando quem pediu a lista/busca de produtos informou
        loja_id, ex.: tela de Produtos e PDV rodando num terminal com
        loja fixa configurada (ver resolver_loja_id/endpoint_com_loja).
        Produto sem linha em EstoqueLoja ainda (nunca teve movimento
        nessa loja) conta como 0, nao como o agregado."""

        if not produto_ids:
            return {}

        linhas = (
            db.query(EstoqueLoja.produto_id, EstoqueLoja.quantidade)
            .filter(
                EstoqueLoja.produto_id.in_(produto_ids),
                EstoqueLoja.loja_id == loja_id,
            )
            .all()
        )

        return {produto_id: quantidade for produto_id, quantidade in linhas}

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
