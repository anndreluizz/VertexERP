from sqlalchemy.orm import Session

from app.models.movimento_caixa import MovimentoCaixa
from app.repositories.caixa_repository import CaixaRepository
from app.repositories.movimento_caixa_repository import (
    MovimentoCaixaRepository,
)
from app.schemas.movimento_caixa import MovimentoCaixaCreate


class MovimentoCaixaService:

    # Unico ponto de entrada publico pra criar um movimento manual de
    # caixa (usado pela tela de sangria/suprimento). VENDA, PAGAMENTO
    # e RECEBIMENTO_FIADO sao criados por dentro de outros services
    # (venda_service, conta_pagar_service, movimento_fiado_service),
    # cada um com sua propria regra de negocio -- deixar esse endpoint
    # aceitar qualquer 'tipo' permitiria fabricar uma "venda" ou um
    # "recebimento de fiado" falso sem lastro nenhum, so inflando os
    # relatorios. Por isso so os dois tipos que a tela realmente usa
    # sao aceitos aqui.
    _TIPOS_PERMITIDOS = {"SANGRIA", "SUPRIMENTO"}

    @staticmethod
    def criar(
        db: Session,
        dados: MovimentoCaixaCreate,
        usuario_id: int,
        loja_id: int | None = None,
    ):

        tipo = dados.tipo.upper()

        if tipo not in MovimentoCaixaService._TIPOS_PERMITIDOS:
            raise Exception(
                'Tipo de movimento inválido. Use "sangria" ou '
                '"suprimento".'
            )

        if dados.valor <= 0:
            raise Exception("Informe um valor maior que zero.")

        caixa = CaixaRepository.buscar_aberto(db, usuario_id, loja_id)

        if not caixa:
            raise Exception("Não existe caixa aberto.")

        movimento = MovimentoCaixa(
            caixa_id=caixa.id,
            usuario_id=usuario_id,
            tipo=tipo,
            descricao=dados.descricao,
            valor=dados.valor,
        )

        if tipo == "SUPRIMENTO":
            caixa.saldo_final += movimento.valor
        else:
            caixa.saldo_final -= movimento.valor

        CaixaRepository.atualizar(db, caixa)

        return MovimentoCaixaRepository.criar(
            db,
            movimento
        )

    @staticmethod
    def listar(db: Session, skip: int = 0, limit: int = 100):
        return MovimentoCaixaRepository.listar(db, skip, limit)

    @staticmethod
    def listar_por_caixa(
        db: Session,
        caixa_id: int,
    ):
        return MovimentoCaixaRepository.listar_por_caixa(
            db,
            caixa_id
        )

    @staticmethod
    def listar_por_tipo(db: Session, tipo: str):
        return MovimentoCaixaRepository.listar_por_tipo(db, tipo)