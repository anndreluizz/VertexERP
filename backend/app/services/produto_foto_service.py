from sqlalchemy.orm import Session

from app.models.produto_foto import ProdutoFoto
from app.repositories.produto_foto_repository import ProdutoFotoRepository
from app.repositories.produto_repository import ProdutoRepository
from app.schemas.produto import ProdutoFotoCreate
from app.utils.imagem import decodificar_foto


class ProdutoFotoService:

    @staticmethod
    def listar(db: Session, produto_id: int):
        return ProdutoFotoRepository.listar_por_produto(db, produto_id)

    @staticmethod
    def adicionar(db: Session, produto_id: int, dados: ProdutoFotoCreate):

        produto = ProdutoRepository.buscar_por_id(db, produto_id)

        if not produto:
            raise Exception("Produto não encontrado.")

        fotos_existentes = ProdutoFotoRepository.listar_por_produto(
            db, produto_id
        )

        # a primeira foto de um produto e' sempre principal, nao
        # importa o que o chamador mandou -- nunca faz sentido um
        # produto com foto nenhuma marcada como principal
        eh_principal = dados.principal or not fotos_existentes

        if eh_principal and fotos_existentes:
            ProdutoFotoRepository.desmarcar_principal_do_produto(
                db, produto_id
            )

        foto = ProdutoFoto(
            produto_id=produto_id,
            imagem=decodificar_foto(dados.imagem_base64),
            ordem=ProdutoFotoRepository.maior_ordem(db, produto_id) + 1,
            principal=eh_principal,
        )

        return ProdutoFotoRepository.criar(db, foto)

    @staticmethod
    def remover(db: Session, produto_id: int, foto_id: int):

        foto = ProdutoFotoRepository.buscar_por_id(db, foto_id)

        if not foto or foto.produto_id != produto_id:
            raise Exception("Foto não encontrada.")

        era_principal = foto.principal

        ProdutoFotoRepository.excluir(db, foto)

        if era_principal:
            restantes = ProdutoFotoRepository.listar_por_produto(
                db, produto_id
            )
            if restantes:
                restantes[0].principal = True
                ProdutoFotoRepository.atualizar(db, restantes[0])

        return {"mensagem": "Foto removida com sucesso."}

    @staticmethod
    def marcar_principal(db: Session, produto_id: int, foto_id: int):

        foto = ProdutoFotoRepository.buscar_por_id(db, foto_id)

        if not foto or foto.produto_id != produto_id:
            raise Exception("Foto não encontrada.")

        ProdutoFotoRepository.desmarcar_principal_do_produto(db, produto_id)

        foto.principal = True

        return ProdutoFotoRepository.atualizar(db, foto)
