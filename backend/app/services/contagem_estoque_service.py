from datetime import datetime

from sqlalchemy.orm import Session

from app.models.contagem_estoque import ContagemEstoque
from app.models.item_contagem_estoque import ItemContagemEstoque
from app.repositories.contagem_estoque_repository import (
    ContagemEstoqueRepository,
)
from app.repositories.item_contagem_estoque_repository import (
    ItemContagemEstoqueRepository,
)
from app.repositories.produto_repository import ProdutoRepository
from app.repositories.estoque_loja_repository import EstoqueLojaRepository
from app.schemas.contagem_estoque import ContagemEstoqueCreate
from app.schemas.movimento_estoque import MovimentoEstoqueCreate
from app.services.movimento_estoque_service import MovimentoEstoqueService


class ContagemEstoqueService:

    @staticmethod
    def abrir(
        db: Session,
        dados: ContagemEstoqueCreate,
        usuario_id: int,
        loja_id: int | None,
    ):
        if loja_id is None:
            raise Exception(
                "Contagem de inventário precisa de uma loja definida."
            )

        if ContagemEstoqueRepository.buscar_aberta(db, loja_id):
            raise Exception("Já existe uma contagem aberta para essa loja.")

        # so' entram produtos ativos visiveis dessa loja (globais +
        # exclusivos) -- limit bem acima do maximo da API porque aqui e'
        # uma foto completa do catalogo, nao uma pagina de listagem
        produtos = [
            p
            for p in ProdutoRepository.listar(
                db, skip=0, limit=100_000, loja_id=loja_id
            )
            if p.ativo
        ]

        quantidades = EstoqueLojaRepository.quantidades_por_loja(
            db, [p.id for p in produtos], loja_id
        )

        contagem = ContagemEstoque(
            loja_id=loja_id,
            usuario_id=usuario_id,
            observacao=dados.observacao,
        )
        contagem.itens = [
            ItemContagemEstoque(
                produto_id=p.id,
                quantidade_sistema=quantidades.get(p.id, 0),
            )
            for p in produtos
        ]

        return ContagemEstoqueRepository.criar(db, contagem)

    @staticmethod
    def buscar_aberta(db: Session, loja_id: int | None):
        if loja_id is None:
            return None
        return ContagemEstoqueRepository.buscar_aberta(db, loja_id)

    @staticmethod
    def buscar_por_id(db: Session, contagem_id: int):
        contagem = ContagemEstoqueRepository.buscar_por_id(db, contagem_id)

        if not contagem:
            raise Exception("Contagem não encontrada.")

        return contagem

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return ContagemEstoqueRepository.listar(db, skip, limit)

    @staticmethod
    def registrar_item(
        db: Session, contagem_id: int, item_id: int, quantidade_contada: int
    ):
        contagem = ContagemEstoqueService.buscar_por_id(db, contagem_id)

        if contagem.status != "ABERTA":
            raise Exception("Essa contagem já foi encerrada.")

        item = ItemContagemEstoqueRepository.buscar_por_id(db, item_id)

        if not item or item.contagem_id != contagem_id:
            raise Exception("Item não encontrado nessa contagem.")

        if quantidade_contada < 0:
            raise Exception("Quantidade contada não pode ser negativa.")

        item.quantidade_contada = quantidade_contada

        return ItemContagemEstoqueRepository.atualizar(db, item)

    @staticmethod
    def finalizar(db: Session, contagem_id: int, usuario_id: int):
        contagem = ContagemEstoqueService.buscar_por_id(db, contagem_id)

        if contagem.status != "ABERTA":
            raise Exception("Essa contagem já foi encerrada.")

        for item in contagem.itens:
            if item.quantidade_contada is None:
                continue
            if item.quantidade_contada == item.quantidade_sistema:
                continue

            MovimentoEstoqueService.criar(
                db,
                MovimentoEstoqueCreate(
                    produto_id=item.produto_id,
                    tipo="AJUSTE",
                    quantidade=item.quantidade_contada,
                    motivo=f"Contagem de inventário #{contagem.id}",
                ),
                usuario_id,
                contagem.loja_id,
            )

        contagem.status = "FINALIZADA"
        contagem.finalizado_em = datetime.now()

        return ContagemEstoqueRepository.atualizar(db, contagem)

    @staticmethod
    def cancelar(db: Session, contagem_id: int):
        contagem = ContagemEstoqueService.buscar_por_id(db, contagem_id)

        if contagem.status != "ABERTA":
            raise Exception("Essa contagem já foi encerrada.")

        contagem.status = "CANCELADA"

        return ContagemEstoqueRepository.atualizar(db, contagem)
