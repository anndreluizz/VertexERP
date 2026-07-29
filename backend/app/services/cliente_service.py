from sqlalchemy.orm import Session

from app.schemas.cliente import ClienteUpdate
from app.models.cliente import Cliente
from app.schemas.cliente import ClienteCreate
from app.repositories.cliente_repository import ClienteRepository


class ClienteService:

    @staticmethod
    def criar(db: Session, dados: ClienteCreate):

        if dados.cpf_cnpj:

            cliente = ClienteRepository.buscar_por_documento(
                db,
                dados.cpf_cnpj
            )

            if cliente:
                raise Exception("CPF/CNPJ já cadastrado.")

        novo_cliente = Cliente(
            nome=dados.nome,
            cpf_cnpj=dados.cpf_cnpj,
            telefone=dados.telefone,
            email=dados.email,
            endereco=dados.endereco,
            cidade=dados.cidade,
            estado=dados.estado,
            ativo=True

        )

        return ClienteRepository.criar(db, novo_cliente)

    @staticmethod
    def listar(db: Session):
        return ClienteRepository.listar(db)

    @staticmethod
    def buscar_por_id(db: Session, cliente_id: int):
        return ClienteRepository.buscar_por_id(db, cliente_id)

    @staticmethod
    def atualizar(
            db: Session,
            cliente_id: int,
            dados: ClienteUpdate
    ):

        cliente = ClienteRepository.buscar_por_id(
            db,
            cliente_id
        )

        if not cliente:
            raise Exception("Cliente não encontrado.")

        for campo, valor in dados.dict(exclude_unset=True).items():
            setattr(cliente, campo, valor)

        return ClienteRepository.atualizar(db, cliente)

    @staticmethod
    def excluir(
            db: Session,
            cliente_id: int
    ):

        cliente = ClienteRepository.buscar_por_id(
            db,
            cliente_id
        )

        if not cliente:
            raise Exception("Cliente não encontrado.")

        cliente.ativo = False

        ClienteRepository.atualizar(db, cliente)

        return {
            "mensagem": "Cliente desativado com sucesso."
        }
