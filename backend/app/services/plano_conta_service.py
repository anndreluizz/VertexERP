from sqlalchemy.orm import Session

from app.models.plano_conta import PlanoConta
from app.schemas.plano_conta import PlanoContaCreate, PlanoContaUpdate
from app.repositories.plano_conta_repository import (
    PlanoContaRepository,
)

_TIPOS_VALIDOS = ("RECEITA", "DESPESA")


def _validar_pai(db: Session, conta_pai_id: int, tipo: str) -> PlanoConta:
    pai = PlanoContaRepository.buscar_por_id(db, conta_pai_id)

    if not pai or not pai.ativo:
        raise Exception("Conta pai não encontrada.")

    if pai.tipo != tipo:
        raise Exception(
            "A subconta precisa ser do mesmo tipo (Receita/Despesa) "
            "da conta pai."
        )

    return pai


def _verificar_ciclo(db: Session, conta_id: int, novo_pai_id: int):
    """Sobe a cadeia de pais a partir de novo_pai_id -- se chegar em
    conta_id de volta, o novo pai escolhido e' descendente da propria
    conta (ou ela mesma), o que criaria um loop infinito em qualquer
    coisa que percorra a arvore pra cima ou pra baixo."""

    atual = PlanoContaRepository.buscar_por_id(db, novo_pai_id)

    while atual is not None:
        if atual.id == conta_id:
            raise Exception(
                "Essa conta não pode ser subconta de uma das suas "
                "próprias subcontas."
            )
        atual = (
            PlanoContaRepository.buscar_por_id(db, atual.conta_pai_id)
            if atual.conta_pai_id is not None
            else None
        )


class PlanoContaService:

    @staticmethod
    def listar(db: Session):
        return PlanoContaRepository.listar(db)

    @staticmethod
    def criar(db: Session, dados: PlanoContaCreate):

        if dados.tipo not in _TIPOS_VALIDOS:
            raise Exception('Tipo precisa ser "RECEITA" ou "DESPESA".')

        if dados.conta_pai_id is not None:
            _validar_pai(db, dados.conta_pai_id, dados.tipo)

        conta = PlanoConta(
            codigo=dados.codigo,
            nome=dados.nome,
            tipo=dados.tipo,
            conta_pai_id=dados.conta_pai_id,
        )

        return PlanoContaRepository.criar(db, conta)

    @staticmethod
    def atualizar(db: Session, conta_id: int, dados: PlanoContaUpdate):

        conta = PlanoContaRepository.buscar_por_id(db, conta_id)

        if not conta:
            raise Exception("Conta não encontrada.")

        if dados.tipo not in _TIPOS_VALIDOS:
            raise Exception('Tipo precisa ser "RECEITA" ou "DESPESA".')

        if dados.conta_pai_id is not None:

            if dados.conta_pai_id == conta_id:
                raise Exception(
                    "Uma conta não pode ser pai de si mesma."
                )

            _validar_pai(db, dados.conta_pai_id, dados.tipo)
            _verificar_ciclo(db, conta_id, dados.conta_pai_id)

        conta.codigo = dados.codigo
        conta.nome = dados.nome
        conta.tipo = dados.tipo
        conta.conta_pai_id = dados.conta_pai_id
        conta.ativo = dados.ativo

        return PlanoContaRepository.atualizar(db, conta)

    @staticmethod
    def excluir(db: Session, conta_id: int):

        conta = PlanoContaRepository.buscar_por_id(db, conta_id)

        if not conta:
            raise Exception("Conta não encontrada.")

        if PlanoContaRepository.listar_filhos_ativos(db, conta_id):
            raise Exception(
                "Essa conta tem subcontas ativas -- exclua ou mova "
                "elas primeiro."
            )

        # soft-delete: contas a pagar ja lancadas podem apontar pra
        # esse plano_conta_id, apagar de vez quebraria a integridade
        # referencial (mesmo padrao ja usado em Produto/Cliente)
        conta.ativo = False

        return PlanoContaRepository.atualizar(db, conta)
