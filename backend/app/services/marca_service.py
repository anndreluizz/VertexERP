from sqlalchemy.orm import Session

from app.models.marca import Marca
from app.schemas.marca import MarcaCreate, MarcaUpdate
from app.repositories.marca_repository import MarcaRepository


class MarcaService:

    @staticmethod
    def criar(db: Session, dados: MarcaCreate):

        marca = MarcaRepository.buscar_por_nome(
            db,
            dados.nome
        )

        if marca:
            raise Exception("Marca já cadastrada.")

        nova_marca = Marca(
            nome=dados.nome,
            descricao=dados.descricao,
            ativo=True
        )

        return MarcaRepository.criar(db, nova_marca)

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return MarcaRepository.listar(db, skip, limit)

    @staticmethod
    def buscar_por_id(db: Session, marca_id: int):
        return MarcaRepository.buscar_por_id(db, marca_id)

    @staticmethod
    def atualizar(
        db: Session,
        marca_id: int,
        dados: MarcaUpdate
    ):

        marca = MarcaRepository.buscar_por_id(
            db,
            marca_id
        )

        if not marca:
            raise Exception("Marca não encontrada.")

        campos = dados.dict(exclude_unset=True)

        novo_nome = campos.get("nome")
        if novo_nome and novo_nome != marca.nome:
            existente = MarcaRepository.buscar_por_nome(db, novo_nome)
            if existente and existente.id != marca_id:
                raise Exception("Marca já cadastrada.")

        for campo, valor in campos.items():
            setattr(marca, campo, valor)

        return MarcaRepository.atualizar(db, marca)

    @staticmethod
    def excluir(db: Session, marca_id: int):

        marca = MarcaRepository.buscar_por_id(
            db,
            marca_id
        )

        if not marca:
            raise Exception("Marca não encontrada.")

        MarcaRepository.excluir(db, marca)

        return {
            "mensagem": "Marca excluída com sucesso."
        }
