from sqlalchemy.orm import Session

from app.auth.permissoes import PERMISSOES_DISPONIVEIS
from app.models.perfil import Perfil
from app.models.user import User
from app.repositories.perfil_repository import PerfilRepository
from app.schemas.perfil import PerfilCreate, PerfilUpdate


def _validar_permissoes(permissoes: list[str]):
    desconhecidas = set(permissoes) - set(PERMISSOES_DISPONIVEIS)
    if desconhecidas:
        raise Exception(
            f"Permissão(ões) inválida(s): {', '.join(sorted(desconhecidas))}."
        )


class PerfilService:

    @staticmethod
    def listar(db: Session):
        return PerfilRepository.listar(db)

    @staticmethod
    def criar(db: Session, dados: PerfilCreate):

        if PerfilRepository.buscar_por_nome(db, dados.nome):
            raise Exception("Já existe um perfil com esse nome.")

        _validar_permissoes(dados.permissoes)

        perfil = Perfil(nome=dados.nome, permissoes=dados.permissoes)

        return PerfilRepository.criar(db, perfil)

    @staticmethod
    def atualizar(db: Session, perfil_id: int, dados: PerfilUpdate):

        perfil = PerfilRepository.buscar_por_id(db, perfil_id)

        if not perfil:
            raise Exception("Perfil não encontrado.")

        duplicado = PerfilRepository.buscar_por_nome(db, dados.nome)
        if duplicado and duplicado.id != perfil_id:
            raise Exception("Já existe um perfil com esse nome.")

        _validar_permissoes(dados.permissoes)

        perfil.nome = dados.nome
        perfil.permissoes = dados.permissoes

        return PerfilRepository.atualizar(db, perfil)

    @staticmethod
    def excluir(db: Session, perfil_id: int):

        perfil = PerfilRepository.buscar_por_id(db, perfil_id)

        if not perfil:
            raise Exception("Perfil não encontrado.")

        em_uso = (
            db.query(User).filter(User.perfil_id == perfil_id).count()
        )
        if em_uso:
            raise Exception(
                f"Esse perfil está atribuído a {em_uso} usuário(s) -- "
                "troque o perfil deles antes de excluir."
            )

        PerfilRepository.excluir(db, perfil)
