import base64

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
            data_nascimento=dados.data_nascimento,
            limite_credito=dados.limite_credito,
            ativo=True

        )

        if dados.foto_base64:
            novo_cliente.foto = base64.b64decode(dados.foto_base64)

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

        campos = dados.dict(exclude_unset=True, exclude={"foto_base64"})

        for campo, valor in campos.items():
            setattr(cliente, campo, valor)

        if dados.foto_base64:
            cliente.foto = base64.b64decode(dados.foto_base64)

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
